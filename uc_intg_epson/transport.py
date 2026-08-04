"""Transport abstraction for Epson projector control.

An Epson projector may be controllable over PJLink (TCP 4352), Epson's native
ESC/VP.net (TCP 3629), or Epson Web Control HTTP (port 80). A given projector
usually speaks one of these - business models tend to have PJLink, consumer
home-cinema models often only expose ESC/VP.net / Web Control. Each transport
implements the same async interface and returns the same dataclasses so the
device layer is protocol-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from uc_intg_epson import const

# Protocol identifiers (stored in config.protocol)
PROTOCOL_AUTO = "auto"
PROTOCOL_PJLINK = "pjlink"
PROTOCOL_ESCVPNET = "escvpnet"
PROTOCOL_WEBCONTROL = "webcontrol"

PROTOCOLS = (PROTOCOL_AUTO, PROTOCOL_PJLINK, PROTOCOL_ESCVPNET, PROTOCOL_WEBCONTROL)


@dataclass
class ProjectorStatus:
    """A polled snapshot of the projector's dynamic state."""

    power: str = const.STATE_UNAVAILABLE
    reachable: bool = False
    source: str = ""                 # friendly input name (already mapped)
    av_muted: bool = False
    lamp_hours: int | None = None
    color_mode: str | None = None
    errors: dict[str, str] = field(default_factory=dict)
    has_error: bool = False


@dataclass
class ProjectorIdentity:
    """Static device information (queried once)."""

    name: str = ""
    manufacturer: str = ""
    product: str = ""
    serial: str = ""
    sw_version: str = ""
    rec_resolution: str = ""
    filter_model: str = ""
    source_names: list[str] = field(default_factory=list)
    color_mode_list: list[str] = field(default_factory=list)


class TransportAuthError(Exception):
    """Raised when the transport rejects the supplied credentials."""


class Transport:
    """Common async interface implemented by every protocol client."""

    name: str = "transport"
    supports_color_mode: bool = False

    async def probe(self) -> bool:
        """Return True if the projector answers on this transport."""
        raise NotImplementedError

    async def get_identity(self) -> ProjectorIdentity:
        raise NotImplementedError

    async def poll(self) -> ProjectorStatus:
        raise NotImplementedError

    async def power_on(self) -> None:
        raise NotImplementedError

    async def power_off(self) -> None:
        raise NotImplementedError

    async def select_source(self, name: str) -> bool:
        return False

    async def set_av_mute(self, muted: bool) -> None:
        raise NotImplementedError

    async def send_raw(self, command: str) -> str:
        raise NotImplementedError

    async def get_color_mode(self) -> str | None:
        return None

    async def set_color_mode(self, name: str) -> bool:
        return False

    async def close(self) -> None:
        return None


def build_candidates(config) -> list[Transport]:
    """Ordered list of transports to try for a device, per config.protocol.

    ``auto`` returns PJLink, then ESC/VP.net, then Web Control. A specific
    protocol returns just that one. Imports are local to avoid an import cycle.
    """
    from uc_intg_epson.escvpnet import ESCVPNetTransport
    from uc_intg_epson.pjlink import PJLinkTransport
    from uc_intg_epson.webcontrol import WebControlTransport

    protocol = getattr(config, "protocol", "") or PROTOCOL_AUTO

    def pjlink() -> Transport:
        return PJLinkTransport(config.host, config.pjlink_port, config.pjlink_password)

    def escvpnet() -> Transport:
        return ESCVPNetTransport(config.host, const.ESCVPNET_PORT, config.web_password)

    def webcontrol() -> Transport:
        return WebControlTransport(config.host, config.web_password)

    if protocol == PROTOCOL_PJLINK:
        return [pjlink()]
    if protocol == PROTOCOL_ESCVPNET:
        return [escvpnet()]
    if protocol == PROTOCOL_WEBCONTROL:
        return [webcontrol()]
    return [pjlink(), escvpnet(), webcontrol()]
