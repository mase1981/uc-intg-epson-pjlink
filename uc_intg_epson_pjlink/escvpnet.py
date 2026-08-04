"""Epson ESC/VP.net client (TCP 3629), best-effort / optional.

Epson's native network protocol. It exposes richer control than PJLink, but on
many units the command channel is gated behind the projector's Web Control /
monitor password (a handshake status of 0x41 = Unauthorized). This client is
therefore optional: the device layer only uses it when the caller opts in, and
every failure degrades gracefully to PJLink + Web Control.

Ported from projector_pilot's ESC/VP.net implementation.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging

from uc_intg_epson_pjlink import const

_LOG = logging.getLogger(__name__)

_TIMEOUT = 4.0
_HELLO = b"ESC/VP.net" + bytes([0x10, 0x03, 0x00, 0x00, 0x00, 0x00])

# Handshake status byte (index 14 of the 16-byte reply)
STATUS_OK = 0x20
STATUS_BAD_REQUEST = 0x40
STATUS_UNAUTHORIZED = 0x41
STATUS_FORBIDDEN = 0x43
STATUS_UNAVAILABLE = 0x45  # standby
STATUS_VERSION = 0x55


class ESCVPNetError(Exception):
    """ESC/VP.net protocol error."""


class ESCVPNetClient:
    """Persistent ESC/VP.net connection to one projector."""

    def __init__(self, host: str, port: int = const.ESCVPNET_PORT, password: str = "") -> None:
        self._host = host
        self._port = port
        self._password = password or ""
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    @property
    def is_connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    def _build_hello(self) -> bytes:
        if not self._password:
            return _HELLO
        digest = hashlib.md5(self._password.encode("utf-8")).hexdigest().encode("ascii")
        return _HELLO + bytes([len(digest)]) + digest

    async def connect(self) -> None:
        async with self._lock:
            if self.is_connected:
                return
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), timeout=_TIMEOUT
            )
            self._writer.write(self._build_hello())
            await self._writer.drain()
            resp = await asyncio.wait_for(self._reader.read(16), timeout=_TIMEOUT)
            status = resp[14] if len(resp) > 14 else STATUS_BAD_REQUEST
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
        if not self.is_connected:
            await self.connect()
        async with self._lock:
            assert self._reader is not None and self._writer is not None
            self._writer.write(f"{verb}\r".encode("ascii"))
            await self._writer.drain()
            raw = await asyncio.wait_for(self._reader.read(128), timeout=_TIMEOUT)
            text = raw.decode("utf-8", errors="replace").strip()
            if not text or text.upper().startswith("ERR"):
                return None
            if ":" in text and "=" in text:
                return text.split("=", 1)[1].split(":", 1)[0].strip()
            if "=" in text:
                return text.split("=", 1)[1].strip()
            return text

    async def get_power(self) -> str | None:
        return await self._command("PWR?")

    async def power_on(self) -> None:
        await self._command("PWR ON")

    async def power_off(self) -> None:
        await self._command("PWR OFF")

    async def get_color_mode(self) -> str | None:
        return await self._command("CMODE?")

    async def get_source_list(self) -> str | None:
        return await self._command("SOURCELIST?")
