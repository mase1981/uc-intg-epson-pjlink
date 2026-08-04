"""Epson projector media_player entity (power, source, AV-mute)."""

from __future__ import annotations

import logging
from typing import Any

from ucapi import StatusCodes, media_player
from ucapi_framework import MediaPlayerEntity

from uc_intg_epson import const
from uc_intg_epson.config import EpsonConfig
from uc_intg_epson.device import EpsonDevice

_LOG = logging.getLogger(__name__)

FEATURES = [
    media_player.Features.ON_OFF,
    media_player.Features.TOGGLE,
    media_player.Features.SELECT_SOURCE,
    media_player.Features.MUTE_TOGGLE,
    media_player.Features.MUTE,
    media_player.Features.UNMUTE,
]

_STATE_MAP = {
    const.STATE_ON: media_player.States.ON,
    const.STATE_WARMING: media_player.States.ON,
    const.STATE_COOLING: media_player.States.STANDBY,
    const.STATE_OFF: media_player.States.STANDBY,
    const.STATE_STANDBY: media_player.States.STANDBY,
    const.STATE_UNAVAILABLE: media_player.States.UNAVAILABLE,
}


class EpsonMediaPlayer(MediaPlayerEntity):
    """Projector as a media player."""

    def __init__(self, device_config: EpsonConfig, device: EpsonDevice) -> None:
        self._device = device
        entity_id = f"media_player.{device_config.identifier}"
        super().__init__(
            entity_id,
            device_config.name,
            FEATURES,
            {
                media_player.Attributes.STATE: media_player.States.UNKNOWN,
                media_player.Attributes.MUTED: False,
                media_player.Attributes.SOURCE: "",
                media_player.Attributes.SOURCE_LIST: [],
            },
            device_class=media_player.DeviceClasses.TV,
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        state = _STATE_MAP.get(self._device.state, media_player.States.UNKNOWN)
        if state == media_player.States.UNAVAILABLE:
            self.update({media_player.Attributes.STATE: state})
            return
        self.update({
            media_player.Attributes.STATE: state,
            media_player.Attributes.MUTED: self._device.av_muted,
            media_player.Attributes.SOURCE: self._device.source,
            media_player.Attributes.SOURCE_LIST: self._device.source_list,
        })

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict | None = None, *_a: Any
    ) -> StatusCodes:
        try:
            match cmd_id:
                case media_player.Commands.ON:
                    ok = await self._device.power_on()
                case media_player.Commands.OFF:
                    ok = await self._device.power_off()
                case media_player.Commands.TOGGLE:
                    ok = await self._device.toggle_power()
                case media_player.Commands.MUTE_TOGGLE:
                    ok = await self._device.toggle_av_mute()
                case media_player.Commands.MUTE:
                    ok = await self._device.set_av_mute(True)
                case media_player.Commands.UNMUTE:
                    ok = await self._device.set_av_mute(False)
                case media_player.Commands.SELECT_SOURCE:
                    ok = await self._device.select_source((params or {}).get("source", ""))
                    if not ok:
                        return StatusCodes.BAD_REQUEST
                case _:
                    return StatusCodes.NOT_IMPLEMENTED
            return StatusCodes.OK if ok else StatusCodes.SERVER_ERROR
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Command error (%s): %s", entity.id, cmd_id, err)
            return StatusCodes.SERVER_ERROR


def create_media_player(device_config: EpsonConfig, device: EpsonDevice) -> list[EpsonMediaPlayer]:
    return [EpsonMediaPlayer(device_config, device)]
