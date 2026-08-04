"""Epson projector device - PollingDevice over PJLink (+ optional Web Control).

PJLink is the mandatory transport (power, input, AV-mute, lamp/filter hours,
device identity, error status). Web Control is an optional, password-gated
enhancement that adds picture/colour-mode control and a standby power-on path
for units that keep HTTP alive while PJLink is closed.

Projector-off pattern: ``establish_connection`` never raises when the projector
is unreachable; the device reports ``UNAVAILABLE`` (not a hard disconnect) and
the poll loop keeps retrying, so entities stay available and can power it on.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ucapi_framework import PollingDevice

from uc_intg_epson_pjlink import const, model_db, wol
from uc_intg_epson_pjlink.config import EpsonConfig
from uc_intg_epson_pjlink.pjlink import PJLinkAuthError, PJLinkClient, PJLinkIdentity, PJLinkStatus
from uc_intg_epson_pjlink.webcontrol import WebControlClient

_LOG = logging.getLogger(__name__)


class EpsonDevice(PollingDevice):
    """One Epson projector, polled over PJLink."""

    def __init__(self, device_config: EpsonConfig, **kwargs: Any) -> None:
        super().__init__(device_config, poll_interval=10, **kwargs)
        self._device_config = device_config
        self._connect_lock = asyncio.Lock()
        self._pjlink = PJLinkClient(
            device_config.host, device_config.pjlink_port, device_config.pjlink_password
        )
        self._web: WebControlClient | None = None
        if device_config.use_web_control:
            self._web = WebControlClient(device_config.host, device_config.web_password)
        self._status = PJLinkStatus()
        self._identity = PJLinkIdentity()
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
        code = self._status.input_code
        if not code:
            return ""
        return const.PJLINK_INPUT_NAMES.get(code, f"Input {code}")

    @property
    def source_list(self) -> list[str]:
        return [
            const.PJLINK_INPUT_NAMES.get(code, f"Input {code}")
            for code in self._identity.input_codes
        ]

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
        return list(const.WEB_COLOR_MODES.values()) if self._web else []

    @property
    def has_web_control(self) -> bool:
        return self._web is not None

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
    async def establish_connection(self) -> None:
        """Non-raising: load identity once, take one poll; never fail hard."""
        async with self._connect_lock:
            if not self._identity_loaded:
                try:
                    self._identity = await self._pjlink.get_identity()
                    self._identity_loaded = True
                    await self._persist_identity()
                except PJLinkAuthError:
                    _LOG.error("[%s] PJLink authentication failed", self.log_id)
                except Exception as err:  # pylint: disable=broad-exception-caught
                    _LOG.info("[%s] Identity not available yet: %s", self.log_id, err)
            await self._refresh()
        _LOG.info("[%s] Connection established (state=%s)", self.log_id, self.state)

    async def poll_device(self) -> None:
        async with self._connect_lock:
            if not self._identity_loaded:
                try:
                    self._identity = await self._pjlink.get_identity()
                    self._identity_loaded = True
                    await self._persist_identity()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
            await self._refresh()
        self.push_update()

    async def _refresh(self) -> None:
        try:
            self._status = await self._pjlink.poll()
        except PJLinkAuthError:
            _LOG.error("[%s] PJLink authentication failed", self.log_id)
            self._status = PJLinkStatus()
            return
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.debug("[%s] Poll failed: %s", self.log_id, err)
            self._status = PJLinkStatus()
            return

        if self._web and self._status.power in (const.STATE_ON, const.STATE_WARMING):
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
            if self._web:
                await self._web.close()
        await super().disconnect()

    # -- commands ----------------------------------------------------------
    async def power_on(self) -> bool:
        """Wake via WoL (if configured), then PJLink, falling back to Web Control."""
        if self._device_config.mac:
            wol.send_magic_packet(self._device_config.mac)
        ok = False
        try:
            await self._pjlink.power_on()
            ok = True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.info("[%s] PJLink power-on failed (%s); trying Web Control", self.log_id, err)
        if self._web:
            try:
                if await self._web.power_on():
                    ok = True
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.debug("[%s] Web Control power-on failed: %s", self.log_id, err)
        return ok

    async def power_off(self) -> bool:
        ok = False
        try:
            await self._pjlink.power_off()
            ok = True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.info("[%s] PJLink power-off failed: %s", self.log_id, err)
        if not ok and self._web:
            try:
                ok = await self._web.power_off()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        return ok

    async def toggle_power(self) -> bool:
        return await self.power_off() if self.power else await self.power_on()

    async def select_source(self, name: str) -> bool:
        code = self._name_to_input_code(name)
        if code is None:
            _LOG.warning("[%s] Unknown source: %s", self.log_id, name)
            return False
        try:
            await self._pjlink.select_input(code)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Source select failed: %s", self.log_id, err)
            return False

    def _name_to_input_code(self, name: str) -> str | None:
        for code in self._identity.input_codes:
            if const.PJLINK_INPUT_NAMES.get(code, f"Input {code}").lower() == name.lower():
                return code
        # allow selecting by raw code too
        if name in self._identity.input_codes:
            return name
        return None

    async def set_av_mute(self, muted: bool) -> bool:
        try:
            await self._pjlink.set_av_mute(muted)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] AV-mute failed: %s", self.log_id, err)
            return False

    async def toggle_av_mute(self) -> bool:
        return await self.set_av_mute(not self._status.av_muted)

    async def send_raw(self, command: str) -> bool:
        """Backward-compatible raw PJLink passthrough (old remote send_cmd)."""
        try:
            await self._pjlink.send_raw(command)
            return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Raw command '%s' failed: %s", self.log_id, command, err)
            return False

    async def set_color_mode(self, name: str) -> bool:
        if not self._web:
            return False
        try:
            if await self._web.set_color_mode(name):
                self._color_mode = name
                return True
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Colour-mode set failed: %s", self.log_id, err)
        return False
