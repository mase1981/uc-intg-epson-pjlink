"""Epson Web Control HTTP client + transport (port 80).

The same CGI endpoints Home Assistant's ``epson-projector`` library uses:

* ``GET /cgi-bin/json_query?jsoncallback=<CMD>%3F`` -> read a property
* ``GET /cgi-bin/directsend?<CMD>=<value>``          -> send a command

Commands use the ESC/VP21 vocabulary (``PWR``, ``SOURCE``, ``MUTE``, ``CMODE``,
``LAMP`` ...). Access may require HTTP Digest auth (user ``EPSONWEB`` + the Web
Control password). Used either as the primary transport (:class:`WebControlTransport`)
or as a colour-mode supplement to PJLink/ESC/VP.net (:class:`WebControlClient`).
"""

from __future__ import annotations

import logging
import re

import aiohttp

from uc_intg_epson_pjlink import const
from uc_intg_epson_pjlink.digest_auth import DigestAuth
from uc_intg_epson_pjlink.transport import ProjectorIdentity, ProjectorStatus, Transport

_LOG = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=5)


class WebControlClient:
    """Low-level Epson Web Control CGI client."""

    def __init__(self, host: str, password: str = "", username: str = const.WEB_USERNAME) -> None:
        self._host = host
        self._base = f"http://{host}"
        self._auth = DigestAuth(username, password or "")
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=_TIMEOUT)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def _request(self, path: str) -> str | None:
        url = f"{self._base}{path}"
        session = await self._ensure_session()
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
                if resp.status != 401:
                    return None
                challenge = resp.headers.get("WWW-Authenticate", "")
            header = self._auth.build_header("GET", url, challenge)
            if not header:
                return None
            async with session.get(url, headers={"Authorization": header}) as resp2:
                if resp2.status == 200:
                    return await resp2.text()
                _LOG.debug("[%s] Web Control %s -> HTTP %s", self._host, path, resp2.status)
                return None
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOG.debug("[%s] Web Control request failed: %s", self._host, err)
            return None

    @staticmethod
    def _parse_reply(body: str | None) -> str | None:
        if not body:
            return None
        match = re.search(r'"reply"\s*:\s*"([^"]*)"', body)
        if match:
            return match.group(1)
        # Fallback: some firmwares return the bare value in the JSONP callback.
        match = re.search(r'\(\s*"?([^")]+)"?\s*\)', body)
        return match.group(1).strip() if match else None

    async def get_property(self, command: str) -> str | None:
        body = await self._request(f"/cgi-bin/json_query?jsoncallback={command}%3F")
        return self._parse_reply(body)

    async def send_command(self, command: str, value: str) -> bool:
        body = await self._request(f"/cgi-bin/directsend?{command}={value}")
        return body is not None

    async def test(self) -> bool:
        return await self.get_property("PWR") is not None

    async def get_color_mode(self) -> str | None:
        code = await self.get_property("CMODE")
        return const.WEB_COLOR_MODES.get(code.upper()) if code else None

    async def set_color_mode(self, display_name: str) -> bool:
        code = const.WEB_COLOR_MODES_INV.get(display_name)
        return await self.send_command("CMODE", code) if code else False

    async def power_on(self) -> bool:
        return await self.send_command("PWR", "ON")

    async def power_off(self) -> bool:
        return await self.send_command("PWR", "OFF")


class WebControlTransport(Transport):
    """Full control transport over Epson Web Control HTTP."""

    name = "webcontrol"
    supports_color_mode = True

    def __init__(self, host: str, password: str = "") -> None:
        self._host = host
        self._client = WebControlClient(host, password)

    async def close(self) -> None:
        await self._client.close()

    async def probe(self) -> bool:
        try:
            return await self._client.test()
        except Exception:  # pylint: disable=broad-exception-caught
            return False

    async def get_identity(self) -> ProjectorIdentity:
        identity = ProjectorIdentity(manufacturer="Epson")
        serial = await self._client.get_property("SNO")
        if serial:
            identity.serial = serial
        raw = await self._client.get_property("SOURCELIST")
        codes = [t.upper() for t in raw.split() if len(t) == 2] if raw else []
        identity.source_names = [
            const.ESCVP_SOURCE_NAMES.get(c, f"Source {c}") for c in codes
        ] or ["HDMI 1", "HDMI 2"]
        identity.color_mode_list = list(const.WEB_COLOR_MODES.values())
        return identity

    async def poll(self) -> ProjectorStatus:
        status = ProjectorStatus()
        power_code = await self._client.get_property("PWR")
        if power_code is None:
            return status
        status.reachable = True
        status.power = const.ESCVP_POWER.get(power_code.upper(), const.STATE_UNAVAILABLE)
        if status.power in (const.STATE_ON, const.STATE_WARMING):
            src = await self._client.get_property("SOURCE")
            if src:
                status.source = const.ESCVP_SOURCE_NAMES.get(src.upper(), f"Source {src}")
            mute = await self._client.get_property("MUTE")
            status.av_muted = bool(mute and mute.upper() == "ON")
            status.color_mode = await self._client.get_color_mode()
        lamp = await self._client.get_property("LAMP")
        if lamp:
            try:
                status.lamp_hours = int(lamp.split()[0])
            except (ValueError, IndexError):
                pass
        return status

    async def power_on(self) -> None:
        await self._client.power_on()

    async def power_off(self) -> None:
        await self._client.power_off()

    async def select_source(self, name: str) -> bool:
        code = const.ESCVP_SOURCE_NAMES_INV.get(name)
        return await self._client.send_command("SOURCE", code) if code else False

    async def set_av_mute(self, muted: bool) -> None:
        await self._client.send_command("MUTE", "ON" if muted else "OFF")

    async def send_raw(self, command: str) -> str:
        cmd = command.strip()
        if "=" in cmd:
            verb, value = cmd.split("=", 1)
            await self._client.send_command(verb.strip(), value.strip())
        else:
            await self._client.get_property(cmd.rstrip("?"))
        return ""

    async def get_color_mode(self) -> str | None:
        return await self._client.get_color_mode()

    async def set_color_mode(self, name: str) -> bool:
        return await self._client.set_color_mode(name)
