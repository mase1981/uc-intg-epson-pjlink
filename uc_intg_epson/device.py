"""Epson projector device - PollingDevice over a selectable transport.

A projector is controlled via one of three transports (chosen in setup, or
auto-detected): PJLink (TCP 4352), ESC/VP.net (TCP 3629), or Web Control HTTP
(port 80). All implement the same interface, so this layer is protocol-agnostic.
Web Control can additionally supplement PJLink/ESC/VP.net for colour-mode control
when a Web Control password is provided.

Projector-off pattern: ``establish_connection`` never raises when the projector
is unreachable; the device reports ``UNAVAILABLE`` and the poll loop keeps
retrying, so entities stay available and can power it on.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ucapi_framework import PollingDevice

from uc_intg_epson import const, model_db, transport, wol
from uc_intg_epson.config import EpsonConfig
from uc_intg_epson.transport import ProjectorIdentity, ProjectorStatus, TransportAuthError
from uc_intg_epson.webcontrol import WebControlClient

_LOG = logging.getLogger(__name__)


class EpsonDevice(PollingDevice):
    """One Epson projector, polled over its configured transport."""

    def __init__(self, device_config: EpsonConfig, **kwargs: Any) -> None:
        super().__init__(device_config, poll_interval=10, **kwargs)
        self._device_config = device_config
        self._connect_lock = asyncio.Lock()
        self._candidates = transport.build_candidates(device_config)
        self._transport = self._candidates[0]
        self._resolved = False
        # Colour-mode supplement when the primary transport is PJLink and a Web
        # Control password is available (PJLink cannot do colour mode).
        self._web: WebControlClient | None = None
        if device_config.web_password and not self._transport.supports_color_mode:
            self._web = WebControlClient(device_config.host, device_config.web_password)
        self._status = ProjectorStatus()
        self._identity = ProjectorIdentity()
        self._profile = model_db.detect(device_config.model, device_config.name)
        self._color_mode: str | None = None
        self._identity_loaded = False

    # -- identity ----------------------------------------------------------
    @property
    def identifier(self) -> str:
        return self._device_config.identifier

    @property
    def name(self) -> str:
        return self._device_config.name

    @property
    def address(self) -> str:
        return self._device_config.host

    @property
    def log_id(self) -> str:
        return f"{self.name} ({self.address})"

    @property
    def protocol(self) -> str:
        return self._transport.name

    # -- state -------------------------------------------------------------
    @property
    def available(self) -> bool:
        return self._status.reachable

    @property
    def state(self) -> str:
        if not self._status.reachable:
            return const.STATE_UNAVAILABLE
        return self._status.power

    @property
    def power(self) -> bool:
        return self._status.power in (const.STATE_ON, const.STATE_WARMING)

    @property
    def source(self) -> str:
        return self._status.source

    @property
    def source_list(self) -> list[str]:
        return list(self._identity.source_names)

    @property
    def av_muted(self) -> bool:
        return self._status.av_muted

    @property
    def lamp_hours(self) -> int | None:
        return self._status.lamp_hours

    @property
    def errors(self) -> dict[str, str]:
        return self._status.errors

    @property
    def has_error(self) -> bool:
        return self._status.has_error

    @property
    def error_summary(self) -> str:
        faults = [f"{k}: {v}" for k, v in self._status.errors.items() if v != "OK"]
        return ", ".join(faults) if faults else "OK"

    @property
    def color_mode(self) -> str | None:
        return self._color_mode

    @property
    def color_mode_list(self) -> list[str]:
        if self._transport.supports_color_mode:
            return self._identity.color_mode_list or list(const.WEB_COLOR_MODES.values())
        if self._web:
            return list(const.WEB_COLOR_MODES.values())
        return []

    @property
    def has_web_control(self) -> bool:
        return self._transport.supports_color_mode or self._web is not None

    @property
    def model(self) -> str:
        return self._device_config.model or self._profile.display_name

    @property
    def serial(self) -> str:
        return self._device_config.serial or self._identity.serial

    @property
    def sw_version(self) -> str:
        return self._device_config.sw_version or self._identity.sw_version

    @property
    def filter_model(self) -> str:
        return self._identity.filter_model

    @property
    def light_source_label(self) -> str:
        return self._profile.light_source_label

    # -- lifecycle ---------------------------------------------------------
    async def _resolve_transport(self) -> None:
        """Pick the first candidate transport that answers (auto-detect)."""
        if self._resolved or len(self._candidates) == 1:
            self._resolved = True
            return
        for candidate in self._candidates:
            try:
                if await candidate.probe():
                    self._transport = candidate
                    self._resolved = True
                    _LOG.info("[%s] Using %s transport", self.log_id, candidate.name)
                    return
            except TransportAuthError as err:
                _LOG.warning("[%s] %s needs a password: %s", self.log_id, candidate.name, err)
            except Exception:  # pylint: disable=broad-exception-caught
                continue
        _LOG.info("[%s] No transport reachable yet; will retry", self.log_id)

    async def establish_connection(self) -> None:
        """Non-raising: resolve transport, load identity once, take one poll."""
        async with self._connect_lock:
            await self._resolve_transport()
            if not self._identity_loaded:
                await self._load_identity()
            await self._refresh()
        _LOG.info("[%s] Connection established (state=%s)", self.log_id, self.state)

    async def poll_device(self) -> None:
        async with self._connect_lock:
            if not self._resolved:
                await self._resolve_transport()
            if not self._identity_loaded:
                await self._load_identity()
            await self._refresh()
        self.push_update()

    async def _load_identity(self) -> None:
        try:
            self._identity = await self._transport.get_identity()
            self._identity_loaded = True
            await self._persist_identity()
        except TransportAuthError:
            _LOG.error("[%s] Authentication failed on %s", self.log_id, self._transport.name)
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.info("[%s] Identity not available yet: %s", self.log_id, err)

    async def _refresh(self) -> None:
        try:
            self._status = await self._transport.poll()
        except TransportAuthError:
            _LOG.error("[%s] Authentication failed on %s", self.log_id, self._transport.name)
            self._status = ProjectorStatus()
            return
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.debug("[%s] Poll failed: %s", self.log_id, err)
            self._status = ProjectorStatus()
            return

        on = self._status.power in (const.STATE_ON, const.STATE_WARMING)
        if self._status.color_mode is not None:
            self._color_mode = self._status.color_mode
        elif self._web and on:
            try:
                self._color_mode = await self._web.get_color_mode()
            except Exception:  # pylint: disable=broad-exception-caught
                self._color_mode = None

    async def _persist_identity(self) -> None:
        updates: dict[str, Any] = {}
        if self._identity.product and not self._device_config.model:
            self._profile = model_db.detect(self._identity.product, self._identity.name)
            updates["model"] = self._profile.display_name
            updates["model_key"] = self._profile.key
        if self._identity.serial and self._identity.serial != self._device_config.serial:
            updates["serial"] = self._identity.serial
        if self._identity.sw_version and self._identity.sw_version != self._device_config.sw_version:
            updates["sw_version"] = self._identity.sw_version
        if updates:
            try:
                self.update_config(**updates)
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.debug("[%s] Could not persist identity: %s", self.log_id, err)

    async def disconnect(self) -> None:
        async with self._connect_lock:
            for candidate in self._candidates:
                try:
                    await candidate.close()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
            if self._web:
                await self._web.close()
        await super().disconnect()

    # -- commands ----------------------------------------------------------
    async def power_on(self) -> bool:
        """Wake via WoL (if configured), then the transport, then Web supplement."""
        if self._device_config.mac:
            wol.send_magic_packet(self._device_config.mac)
        ok = False
        try:
            await self._transport.power_on()
            ok = True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.info("[%s] %s power-on failed: %s", self.log_id, self._transport.name, err)
        if self._web:
            try:
                if await self._web.power_on():
                    ok = True
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        return ok

    async def power_off(self) -> bool:
        ok = False
        try:
            await self._transport.power_off()
            ok = True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.info("[%s] %s power-off failed: %s", self.log_id, self._transport.name, err)
        if not ok and self._web:
            try:
                ok = await self._web.power_off()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        return ok

    async def toggle_power(self) -> bool:
        return await self.power_off() if self.power else await self.power_on()

    async def select_source(self, name: str) -> bool:
        try:
            if await self._transport.select_source(name):
                return True
            _LOG.warning("[%s] Unknown source: %s", self.log_id, name)
            return False
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Source select failed: %s", self.log_id, err)
            return False

    async def set_av_mute(self, muted: bool) -> bool:
        try:
            await self._transport.set_av_mute(muted)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] AV-mute failed: %s", self.log_id, err)
            return False

    async def toggle_av_mute(self) -> bool:
        return await self.set_av_mute(not self._status.av_muted)

    async def send_raw(self, command: str) -> bool:
        try:
            await self._transport.send_raw(command)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Raw command '%s' failed: %s", self.log_id, command, err)
            return False

    async def set_color_mode(self, name: str) -> bool:
        target = self._transport if self._transport.supports_color_mode else None
        try:
            if target is not None and await target.set_color_mode(name):
                self._color_mode = name
                return True
            if self._web and await self._web.set_color_mode(name):
                self._color_mode = name
                return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Colour-mode set failed: %s", self.log_id, err)
        return False
