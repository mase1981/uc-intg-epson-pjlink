"""Integration driver for Epson projectors (PJLink + Web Control)."""

from __future__ import annotations

from ucapi_framework import BaseIntegrationDriver

from uc_intg_epson_pjlink.config import EpsonConfig
from uc_intg_epson_pjlink.device import EpsonDevice
from uc_intg_epson_pjlink.media_player import create_media_player
from uc_intg_epson_pjlink.remote import create_remote
from uc_intg_epson_pjlink.select import create_selects
from uc_intg_epson_pjlink.sensor import create_sensors


class EpsonDriver(BaseIntegrationDriver[EpsonDevice, EpsonConfig]):
    """Builds a media_player, remote, selects and sensors per projector."""

    def __init__(self) -> None:
        super().__init__(
            device_class=EpsonDevice,
            entity_classes=[
                create_media_player,
                create_remote,
                create_selects,
                create_sensors,
            ],
            driver_id="uc-intg-epson-pj",
        )
