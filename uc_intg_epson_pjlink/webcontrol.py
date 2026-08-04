"""Epson Web Control HTTP client (optional, password-gated).

Uses the projector's built-in Web Control CGI (the same endpoints HA's
``epson-projector`` library uses):

* ``GET /cgi-bin/json_query?jsoncallback=<CMD>%3F`` -> reads a property
* ``GET /cgi-bin/directsend?<CMD>=<value>``          -> sends a command

Access requires HTTP Digest auth (user ``EPSONWEB`` + the Web Control
password). This client is best-effort: any failure returns ``None``/``False``
and the integration falls back to PJLink. It adds picture/colour-mode control
and can power the projector on when the PJLink port is closed in standby.
"""

from __future__ import annotations

import logging

import aiohttp

from uc_intg_epson_pjlink import const
from uc_intg_epson_pjlink.digest_auth import DigestAuth

_LOG = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=5)


class WebControlClient:
    """Talks to the Epson Web Control CGI over HTTP."""

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
        """GET with a digest retry; returns the body text or None on failure."""
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
        """Extract ``reply`` from the json_query JSONP-ish response body."""
        if not body:
            return None
        # Body looks like: <CMD>({"projector":{"feature":{"reply":"01", ...}}})
        import re

        match = re.search(r'"reply"\s*:\s*"([^"]*)"', body)
        return match.group(1) if match else None

    async def test(self) -> bool:
        """Return True if Web Control answers an authenticated power query."""
        return await self.get_property("PWR") is not None

    async def get_property(self, command: str) -> str | None:
        body = await self._request(f"/cgi-bin/json_query?jsoncallback={command}%3F")
        return self._parse_reply(body)

    async def send_command(self, command: str, value: str) -> bool:
        body = await self._request(f"/cgi-bin/directsend?{command}={value}")
        return body is not None

    # -- high-level helpers -------------------------------------------------
    async def get_power_code(self) -> str | None:
        return await self.get_property("PWR")

    async def power_on(self) -> bool:
        return await self.send_command("PWR", "ON")

    async def power_off(self) -> bool:
        return await self.send_command("PWR", "OFF")

    async def get_color_mode(self) -> str | None:
        code = await self.get_property("CMODE")
        if code is None:
            return None
        return const.WEB_COLOR_MODES.get(code.upper(), None)

    async def set_color_mode(self, display_name: str) -> bool:
        code = const.WEB_COLOR_MODES_INV.get(display_name)
        if code is None:
            return False
        return await self.send_command("CMODE", code)

    async def get_aspect(self) -> str | None:
        code = await self.get_property("ASPECT")
        if code is None:
            return None
        return const.WEB_ASPECT_MODES.get(code.upper(), None)
