"""Epson ESC/VP.net transport (TCP 3629).

Epson's native network control protocol - the one Home Assistant's
``epson-projector`` library uses for consumer home-cinema models that do not
expose PJLink. Handshake, then plain ESC/VP21 commands (``PWR?``, ``SOURCE 30``,
``MUTE ON`` ...) terminated with CR, responses delimited by ``:``.

Some units gate the command channel behind the projector's monitor/Web Control
password (handshake status 0x41 = Unauthorized); a password is appended to the
handshake when configured.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re

from uc_intg_epson import const
from uc_intg_epson.transport import (
    ProjectorIdentity,
    ProjectorStatus,
    Transport,
    TransportAuthError,
)

_LOG = logging.getLogger(__name__)

_TIMEOUT = 5.0
_HELLO = b"ESC/VP.net" + bytes([0x10, 0x03, 0x00, 0x00, 0x00, 0x00])

STATUS_OK = 0x20
STATUS_UNAUTHORIZED = 0x41
STATUS_UNAVAILABLE = 0x45  # standby


class ESCVPNetError(Exception):
    """ESC/VP.net protocol error."""


class ESCVPNetTransport(Transport):
    """ESC/VP.net control transport for one projector."""

    name = "escvpnet"
    supports_color_mode = True

    def __init__(self, host: str, port: int = const.ESCVPNET_PORT, password: str = "") -> None:
        self._host = host
        self._port = port
        self._password = password or ""
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    @property
    def _connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    def _build_hello(self) -> bytes:
        if not self._password:
            return _HELLO
        digest = hashlib.md5(self._password.encode("utf-8")).hexdigest().encode("ascii")
        return _HELLO + bytes([len(digest)]) + digest

    async def _connect(self) -> None:
        if self._connected:
            return
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port), timeout=_TIMEOUT
        )
        self._writer.write(self._build_hello())
        await self._writer.drain()
        resp = await asyncio.wait_for(self._reader.read(16), timeout=_TIMEOUT)
        status = resp[14] if len(resp) > 14 else 0x40
        if status == STATUS_UNAUTHORIZED:
            await self._close_locked()
            raise TransportAuthError("ESC/VP.net requires the Web Control/monitor password")
        if status != STATUS_OK:
            await self._close_locked()
            raise ESCVPNetError(f"Handshake failed (status 0x{status:02X})")

    async def _close_locked(self) -> None:
        if self._writer is not None:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        self._reader = None
        self._writer = None

    async def close(self) -> None:
        async with self._lock:
            await self._close_locked()

    async def _command(self, verb: str) -> str | None:
        """Send one ESC/VP21 verb and return its echoed response value.

        Queries read until the reply echoing the sent verb (``KEY=value``) is
        found, discarding any stale data left in the persistent socket. Without
        this, several commands per poll can desynchronise the socket so that,
        e.g., ``LAMP?`` returns another command's reply.
        """
        verb = verb.strip()
        is_query = verb.endswith("?")
        key = verb.split()[0].rstrip("?").upper()
        async with self._lock:
            try:
                await self._connect()
                assert self._reader is not None and self._writer is not None
                self._writer.write(f"{verb}\r".encode("ascii"))
                await self._writer.drain()
                if not is_query:
                    try:
                        await asyncio.wait_for(self._reader.read(64), timeout=1.5)
                    except asyncio.TimeoutError:
                        pass
                    return ""
                return await asyncio.wait_for(self._read_echo(key), timeout=_TIMEOUT)
            except TransportAuthError:
                raise
            except (OSError, asyncio.TimeoutError) as err:
                await self._close_locked()
                raise ESCVPNetError(str(err)) from err

    async def _read_echo(self, key: str) -> str | None:
        """Read until ``KEY=value`` appears, draining stale/earlier responses."""
        assert self._reader is not None
        pattern = re.compile(re.escape(key) + r"=([^\r\n:]*)", re.IGNORECASE)
        buffer = ""
        while True:
            chunk = await self._reader.read(256)
            if not chunk:
                return None
            buffer += chunk.decode("utf-8", errors="replace")
            match = pattern.search(buffer)
            if match:
                return match.group(1).strip()
            if re.search(r"\bERR\b", buffer, re.IGNORECASE):
                return None

    # -- Transport interface ----------------------------------------------
    async def probe(self) -> bool:
        try:
            await self._command("PWR?")
            return True
        except TransportAuthError:
            raise
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    async def get_identity(self) -> ProjectorIdentity:
        identity = ProjectorIdentity(manufacturer="Epson")
        try:
            serial = await self._command("SNO?")
            if serial:
                identity.serial = serial
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        identity.source_names = await self._source_names()
        identity.color_mode_list = list(const.WEB_COLOR_MODES.values())
        return identity

    async def _source_names(self) -> list[str]:
        try:
            raw = await self._command("SOURCELIST?")
        except Exception:  # pylint: disable=broad-exception-caught
            raw = None
        codes: list[str] = []
        if raw:
            # "30 A0" or "30 HDMI1 A0 HDMI2" -> take 2-char hex tokens
            for token in raw.split():
                if len(token) == 2 and all(c in "0123456789ABCDEFabcdef" for c in token):
                    codes.append(token.upper())
        names = [const.ESCVP_SOURCE_NAMES.get(c, f"Source {c}") for c in codes]
        return names or ["HDMI 1", "HDMI 2"]

    async def poll(self) -> ProjectorStatus:
        status = ProjectorStatus()
        try:
            power_code = await self._command("PWR?")
        except TransportAuthError:
            raise
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.debug("[%s] ESC/VP.net unreachable: %s", self._host, err)
            return status
        if power_code is None:
            return status
        status.reachable = True
        status.power = const.ESCVP_POWER.get(power_code.upper(), const.STATE_UNAVAILABLE)

        if status.power in (const.STATE_ON, const.STATE_WARMING):
            try:
                src = await self._command("SOURCE?")
                if src:
                    status.source = const.ESCVP_SOURCE_NAMES.get(src.upper(), f"Source {src}")
                mute = await self._command("MUTE?")
                status.av_muted = bool(mute and mute.upper() == "ON")
                cmode = await self._command("CMODE?")
                if cmode:
                    status.color_mode = const.WEB_COLOR_MODES.get(cmode.upper())
            except Exception:  # pylint: disable=broad-exception-caught
                pass
        try:
            lamp = await self._command("LAMP?")
            if lamp:
                status.lamp_hours = int(lamp.split()[0])
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return status

    async def power_on(self) -> None:
        await self._command("PWR ON")

    async def power_off(self) -> None:
        await self._command("PWR OFF")

    async def select_source(self, name: str) -> bool:
        code = const.ESCVP_SOURCE_NAMES_INV.get(name)
        if code is None:
            return False
        await self._command(f"SOURCE {code}")
        return True

    async def set_av_mute(self, muted: bool) -> None:
        await self._command("MUTE ON" if muted else "MUTE OFF")

    async def send_raw(self, command: str) -> str:
        # Strip any PJLink framing a legacy activity might send.
        verb = command.strip()
        if verb.startswith("%1") or verb.startswith("%2"):
            verb = verb[2:].strip()
        return await self._command(verb) or ""

    async def get_color_mode(self) -> str | None:
        code = await self._command("CMODE?")
        return const.WEB_COLOR_MODES.get(code.upper()) if code else None

    async def set_color_mode(self, name: str) -> bool:
        code = const.WEB_COLOR_MODES_INV.get(name)
        if code is None:
            return False
        await self._command(f"CMODE {code}")
        return True
