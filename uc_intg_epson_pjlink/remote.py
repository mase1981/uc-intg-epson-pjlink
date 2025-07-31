import logging
import asyncio
from typing import Any

import ucapi
from ucapi import MediaPlayer, Remote, media_player, remote, EntityTypes, StatusCodes
from ucapi.media_player import Attributes as MediaAttr
from ucapi.remote import Attributes as RemoteAttr
from ucapi.media_player import Features as MediaFeatures
from ucapi.remote import Features as RemoteFeatures
from ucapi.media_player import States as MediaStates
from ucapi.remote import States as RemoteStates

from config import EpsonDevice, create_entity_id
from projector import EpsonProjector, PowerState
import const

_LOGGER = logging.getLogger(__name__)

class EpsonMediaPlayer(MediaPlayer):
    def __init__(self, config_device: EpsonDevice, device: EpsonProjector):
        self._device = device
        self.config = config_device
        entity_id = create_entity_id(config_device.identifier, EntityTypes.MEDIA_PLAYER)
        super().__init__(
            identifier=entity_id,
            name=f"{config_device.name}",
            features=[MediaFeatures.ON_OFF],
            attributes={MediaAttr.STATE: device.state},
            cmd_handler=self.command_handler,
        )

    async def command_handler(
        self, entity: MediaPlayer, cmd_id: str, params: dict[str, Any] | None
    ) -> ucapi.StatusCodes:
        if cmd_id == media_player.Commands.ON:
            await self._device.set_power('on')
        elif cmd_id == media_player.Commands.OFF:
            await self._device.set_power('off')
        else:
            return StatusCodes.NOT_IMPLEMENTED
        await asyncio.sleep(2)
        await self._device.update()
        return StatusCodes.OK

class EpsonRemote(Remote):
    def __init__(self, config_device: EpsonDevice, device: EpsonProjector):
        self._device = device
        entity_id = create_entity_id(config_device.identifier, EntityTypes.REMOTE)
        super().__init__(
            identifier=entity_id,
            name=f"{config_device.name} Remote",
            features=[RemoteFeatures.ON_OFF],
            attributes={
                RemoteAttr.STATE: _device_state_to_remote_state(device.state),
            },
            ui_pages=self._create_ui_pages(),
            cmd_handler=self.command_handler,
        )

    def _create_ui_pages(self) -> list[ucapi.ui.UiPage]:
        page1 = ucapi.ui.UiPage("main", "Controls", grid=ucapi.ui.Size(2, 2))
        page1.add(ucapi.ui.create_ui_text("Power On", 0, 0, cmd=remote.Commands.ON))
        page1.add(ucapi.ui.create_ui_text("Power Off", 1, 0, cmd=remote.Commands.OFF))
        page1.add(ucapi.ui.create_ui_text("HDMI 1", 0, 1, cmd=remote.create_send_cmd(const.INPUT_HDMI1)))
        page1.add(ucapi.ui.create_ui_text("HDMI 2", 1, 1, cmd=remote.create_send_cmd(const.INPUT_HDMI2)))
        return [page1]

    async def command_handler(
        self, entity: Remote, cmd_id: str, params: dict[str, Any] | None = None
    ) -> StatusCodes:
        if cmd_id == remote.Commands.ON:
            await self._device.set_power('on')
        elif cmd_id == remote.Commands.OFF:
            await self._device.set_power('off')
        elif cmd_id == remote.Commands.SEND_CMD:
            command_to_send = params.get("command") if params else None
            if command_to_send:
                await self._device.send_raw_command(command_to_send)
            else:
                return StatusCodes.BAD_REQUEST
        else:
            return StatusCodes.NOT_IMPLEMENTED
        await asyncio.sleep(2)
        return StatusCodes.OK

def _device_state_to_remote_state(device_state: PowerState) -> RemoteStates:
    if device_state == PowerState.ON:
        return RemoteStates.ON
    return RemoteStates.OFF