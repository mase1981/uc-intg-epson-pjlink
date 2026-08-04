"""Wake-on-LAN helper - lets the projector be powered on from deep standby.

Some Epson units close the PJLink/Web network stack in standby ("Communication
Off"). A WoL magic packet can wake the network interface so the follow-up
power-on command reaches the projector.
"""

from __future__ import annotations

import logging
import re
import socket

_LOG = logging.getLogger(__name__)


def normalise_mac(mac: str) -> str | None:
    """Return 12 hex chars from a MAC in any common notation, or None."""
    if not mac:
        return None
    hex_only = re.sub(r"[^0-9a-fA-F]", "", mac)
    if len(hex_only) != 12:
        return None
    return hex_only.lower()


def send_magic_packet(mac: str, broadcast: str = "255.255.255.255", port: int = 9) -> bool:
    """Send a Wake-on-LAN magic packet for ``mac``. Returns True on send."""
    normalised = normalise_mac(mac)
    if not normalised:
        _LOG.debug("Invalid MAC for WoL: %r", mac)
        return False
    payload = bytes.fromhex("FF" * 6 + normalised * 16)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(payload, (broadcast, port))
        return True
    except OSError as err:
        _LOG.debug("WoL send failed: %s", err)
        return False
