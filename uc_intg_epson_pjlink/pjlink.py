"""Async PJLink (Class 1/2) client for Epson projectors.

One short-lived TCP connection per command (the PJLink reference behaviour),
serialised through a lock. Handles the optional MD5 authentication handshake
and parses the Epson responses verified on a real QB1000.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field

from uc_intg_epson_pjlink import const

_LOG = logging.getLogger(__name__)

_TIMEOUT = 4.0


class PJLinkError(Exception):
    """Raised for PJLink protocol-level failures (auth, ERR responses)."""


class PJLinkAuthError(PJLinkError):
    """Raised when the projector rejects the supplied PJLink password."""


@dataclass
class PJLinkStatus:
    """A polled snapshot of the projector's dynamic state."""

    power: str = const.STATE_UNAVAILABLE
    reachable: bool = False
    input_code: str | None = None
    av_muted: bool = False
    lamp_hours: int | None = None
    errors: dict[str, str] = field(default_factory=dict)
    has_error: bool = False


@dataclass
class PJLinkIdentity:
    """Static device information (queried once)."""

    name: str = ""
    manufacturer: str = ""
    product: str = ""
    other_info: str = ""
    serial: str = ""
    sw_version: str = ""
    rec_resolution: str = ""
    filter_model: str = ""
    input_codes: list[str] = field(default_factory=list)


class PJLinkClient:
    """Talks PJLink to a single projector."""

    def __init__(self, host: str, port: int = const.PJLINK_PORT, password: str = "") -> None:
        self._host = host
        self._port = port
        self._password = password or ""
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    async def _send(self, command: str) -> str:
        """Open a connection, (optionally) authenticate, send one command, read reply."""
        async with self._lock:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), timeout=_TIMEOUT
            )
            try:
                greeting = (await asyncio.wait_for(reader.read(64), timeout=_TIMEOUT)).decode(
                    "utf-8", errors="replace"
                ).strip()
                payload = command
                if greeting.startswith("PJLINK 1"):
                    parts = greeting.split(" ")
                    if len(parts) < 3:
                        raise PJLinkError("Malformed authentication challenge")
                    seed = parts[2].strip()
                    digest = hashlib.md5((self._password + seed).encode("utf-8")).hexdigest()
                    payload = f"{digest}{command}"
                elif greeting.startswith("PJLINK ERRA"):
                    raise PJLinkAuthError("Authentication required")

                writer.write(f"{payload}\r".encode("utf-8"))
                await writer.drain()
                raw = await asyncio.wait_for(reader.read(256), timeout=_TIMEOUT)
                response = raw.decode("utf-8", errors="replace").strip()
                if "PJLINK ERRA" in response:
                    raise PJLinkAuthError("Invalid PJLink password")
                return response
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

    @staticmethod
    def _value(response: str) -> str | None:
        """Extract the value from an ``%<cmd>=<value>`` reply."""
        if "=" not in response:
            return None
        return response.split("=", 1)[1].strip()

    @staticmethod
    def _is_err(value: str | None) -> bool:
        return value is None or value.upper().startswith("ERR")

    # -- high-level queries -------------------------------------------------
    async def test(self) -> bool:
        """Return True if the projector answers a power query (validates setup)."""
        value = self._value(await self._send(const.CMD_GET_POWER))
        return value is not None

    async def get_power(self) -> str:
        value = self._value(await self._send(const.CMD_GET_POWER))
        if self._is_err(value):
            return const.STATE_UNAVAILABLE
        return const.PJLINK_POWER.get(value, const.STATE_UNAVAILABLE)

    async def get_input(self) -> str | None:
        value = self._value(await self._send(const.CMD_GET_INPUT))
        return None if self._is_err(value) else value

    async def get_av_mute(self) -> bool:
        value = self._value(await self._send(const.CMD_GET_AVMUTE))
        if self._is_err(value):
            return False
        return value in const.AVMUTE_MUTED

    async def get_lamp_hours(self) -> int | None:
        value = self._value(await self._send(const.CMD_GET_LAMP))
        if self._is_err(value):
            return None
        try:
            return int(value.split(" ")[0])
        except (ValueError, IndexError):
            return None

    async def get_errors(self) -> tuple[dict[str, str], bool]:
        value = self._value(await self._send(const.CMD_GET_ERRORS))
        if self._is_err(value) or len(value) < 6:
            return {}, False
        result: dict[str, str] = {}
        has_error = False
        for name, char in zip(const.ERST_COMPONENTS, value[:6]):
            level = const.ERST_LEVELS.get(char, "OK")
            result[name] = level
            if char == "2":
                has_error = True
        return result, has_error

    async def poll(self) -> PJLinkStatus:
        """Fetch a full dynamic snapshot; sets ``reachable`` on TCP success."""
        status = PJLinkStatus()
        try:
            status.power = await self.get_power()
            status.reachable = status.power != const.STATE_UNAVAILABLE
        except PJLinkAuthError:
            raise
        except (OSError, asyncio.TimeoutError, PJLinkError) as err:
            _LOG.debug("[%s] PJLink unreachable: %s", self._host, err)
            return status

        if status.power in (const.STATE_ON, const.STATE_WARMING):
            try:
                status.input_code = await self.get_input()
                status.av_muted = await self.get_av_mute()
            except (OSError, asyncio.TimeoutError, PJLinkError):
                pass
        try:
            status.lamp_hours = await self.get_lamp_hours()
            status.errors, status.has_error = await self.get_errors()
        except (OSError, asyncio.TimeoutError, PJLinkError):
            pass
        return status

    async def get_identity(self) -> PJLinkIdentity:
        """Query the static device information (name, model, serial, inputs...)."""
        identity = PJLinkIdentity()

        async def _q(command: str) -> str:
            value = self._value(await self._send(command))
            return "" if self._is_err(value) else value

        identity.name = await _q(const.CMD_GET_NAME)
        identity.manufacturer = await _q(const.CMD_GET_MANUFACTURER)
        identity.product = await _q(const.CMD_GET_PRODUCT)
        identity.other_info = await _q(const.CMD_GET_OTHER_INFO)
        identity.serial = await _q(const.CMD_GET_SERIAL)
        identity.sw_version = await _q(const.CMD_GET_SW_VERSION)
        identity.rec_resolution = await _q(const.CMD_GET_REC_RESOLUTION)
        identity.filter_model = await _q(const.CMD_GET_FILTER_MODEL)
        inst = await _q(const.CMD_GET_INPUT_LIST)
        identity.input_codes = inst.split() if inst else []
        return identity

    # -- commands -----------------------------------------------------------
    async def power_on(self) -> None:
        await self._send(const.CMD_POWER_ON)

    async def power_off(self) -> None:
        await self._send(const.CMD_POWER_OFF)

    async def select_input(self, code: str) -> None:
        await self._send(const.CMD_SET_INPUT.format(code=code))

    async def set_av_mute(self, muted: bool) -> None:
        await self._send(const.CMD_SET_AVMUTE_ON if muted else const.CMD_SET_AVMUTE_OFF)

    async def send_raw(self, command: str) -> str:
        """Send a raw PJLink command string (e.g. ``%1INPT 32``)."""
        return await self._send(command)
