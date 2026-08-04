"""Minimal HTTP Digest authentication helper for Epson Web Control.

aiohttp has no built-in digest auth, so we do the standard two-step dance:
send the request, parse the ``WWW-Authenticate`` challenge from the 401, then
retry with a computed ``Authorization`` header. MD5 / MD5-sess + qop=auth,
which is what the Epson Web Control CGI uses.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse


def _parse_challenge(header: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in re.finditer(r'(\w+)=(?:"([^"]*)"|([^,\s]+))', header):
        key = match.group(1).lower()
        fields[key] = match.group(2) if match.group(2) is not None else match.group(3)
    return fields


class DigestAuth:
    """Computes Digest ``Authorization`` headers for one credential pair."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._nc = 0

    def build_header(self, method: str, url: str, challenge_header: str) -> str | None:
        challenge = _parse_challenge(challenge_header)
        realm = challenge.get("realm", "")
        nonce = challenge.get("nonce", "")
        qop = challenge.get("qop", "")
        opaque = challenge.get("opaque")
        algorithm = challenge.get("algorithm", "MD5")
        if not nonce:
            return None

        uri = urlparse(url).path or "/"
        if urlparse(url).query:
            uri = f"{uri}?{urlparse(url).query}"

        def md5(text: str) -> str:
            return hashlib.md5(text.encode("utf-8")).hexdigest()

        ha1 = md5(f"{self._username}:{realm}:{self._password}")
        ha2 = md5(f"{method}:{uri}")

        self._nc += 1
        nc_value = f"{self._nc:08x}"
        cnonce = hashlib.md5(f"{nonce}:{nc_value}".encode()).hexdigest()[:16]

        if algorithm.lower() == "md5-sess":
            ha1 = md5(f"{ha1}:{nonce}:{cnonce}")

        if "auth" in qop:
            response = md5(f"{ha1}:{nonce}:{nc_value}:{cnonce}:auth:{ha2}")
        else:
            response = md5(f"{ha1}:{nonce}:{ha2}")

        parts = [
            f'username="{self._username}"',
            f'realm="{realm}"',
            f'nonce="{nonce}"',
            f'uri="{uri}"',
            f'response="{response}"',
        ]
        if "auth" in qop:
            parts += ["qop=auth", f"nc={nc_value}", f'cnonce="{cnonce}"']
        if opaque is not None:
            parts.append(f'opaque="{opaque}"')
        if algorithm:
            parts.append(f"algorithm={algorithm}")
        return "Digest " + ", ".join(parts)
