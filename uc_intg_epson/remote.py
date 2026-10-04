"""Epson projector remote entity - power, inputs and AV-mute for activities."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ucapi import StatusCodes, remote
from ucapi.ui import Buttons, Size, UiPage, create_btn_mapping, create_ui_icon, create_ui_text
from ucapi_framework import RemoteEntity

from uc_intg_epson import const
from uc_intg_epson.config import EpsonConfig
from uc_intg_epson.device import EpsonDevice

_LOG = logging.getLogger(__name__)

SIMPLE_COMMANDS = [
    "POWER", "POWER_ON", "POWER_OFF",
    "HDMI_1", "HDMI_2",
    "AV_MUTE_ON", "AV_MUTE_OFF", "AV_MUTE_TOGGLE",
]


class EpsonRemote(RemoteEntity):
    """Projector power / input / AV-mute as simple commands + a UI page."""

    def __init__(self, device_config: EpsonConfig, device: EpsonDevice) -> None:
        self._device = device
        entity_id = f"remote.{device_config.identifier}"
        super().__init__(
            entity_id,
            f"{device_config.name} Remote",
            [remote.Features.ON_OFF, remote.Features.TOGGLE, remote.Features.SEND_CMD],
            {remote.Attributes.STATE: remote.States.UNKNOWN},
            simple_commands=SIMPLE_COMMANDS,
            button_mapping=[
                create_btn_mapping(Buttons.POWER, short="POWER"),
                create_btn_mapping(Buttons.HOME, short="AV_MUTE_TOGGLE"),
                create_btn_mapping(Buttons.BLUE, short="HDMI_1"),
                create_btn_mapping(Buttons.YELLOW, short="HDMI_2"),
            ],
            ui_pages=[
                UiPage("main", "Projector", grid=Size(4, 6), items=[
                    create_ui_icon("uc:power-on", 0, 0, cmd="POWER_ON"),
                    create_ui_icon("uc:power-off", 3, 0, cmd="POWER_OFF"),
                    create_ui_text("HDMI 1", 0, 2, size=Size(2, 1), cmd="HDMI_1"),
                    create_ui_text("HDMI 2", 2, 2, size=Size(2, 1), cmd="HDMI_2"),
                    create_ui_text("AV Mute", 0, 4, size=Size(2, 1), cmd="AV_MUTE_TOGGLE"),
                    create_ui_text("Show", 2, 4, size=Size(2, 1), cmd="AV_MUTE_OFF"),
                ]),
            ],
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({remote.Attributes.STATE: remote.States.UNAVAILABLE})
            return
        self.update({
            remote.Attributes.STATE: remote.States.ON if self._device.power else remote.States.OFF,
        })

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict | None = None, *_a: Any
    ) -> StatusCodes:
        try:
            if cmd_id == remote.Commands.ON:
                return StatusCodes.OK if await self._device.power_on() else StatusCodes.SERVER_ERROR
            if cmd_id == remote.Commands.OFF:
                return StatusCodes.OK if await self._device.power_off() else StatusCodes.SERVER_ERROR
            if cmd_id == remote.Commands.TOGGLE:
                return StatusCodes.OK if await self._device.toggle_power() else StatusCodes.SERVER_ERROR
            params = params or {}
            if cmd_id == remote.Commands.SEND_CMD:
                commands = [params.get("command", "")]
            elif cmd_id == remote.Commands.SEND_CMD_SEQUENCE:
                commands = params.get("sequence") or []
                if isinstance(commands, str):
                    commands = commands.split(",")
            else:
                return StatusCodes.NOT_IMPLEMENTED
            commands = [str(command).strip() for command in commands if str(command).strip()]
            if not commands:
                return StatusCodes.BAD_REQUEST
            repeat, delay = _repeat_delay(params)
            first = True
            for _ in range(repeat):
                for command in commands:
                    if not first and delay:
                        await asyncio.sleep(delay)
                    first = False
                    status = await self._run(command)
                    if status != StatusCodes.OK:
                        return status
            return StatusCodes.OK
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("[%s] Remote command error (%s): %s", entity.id, cmd_id, err)
            return StatusCodes.SERVER_ERROR

    async def _run(self, command: str) -> StatusCodes:
        # Backward compatibility: the previous integration sent raw PJLink
        # strings (e.g. "%1INPT 32") through send_cmd.
        if command.startswith("%"):
            return StatusCodes.OK if await self._device.send_raw(command) else StatusCodes.SERVER_ERROR

        actions = {
            "POWER": self._device.toggle_power,
            "POWER_ON": self._device.power_on,
            "POWER_OFF": self._device.power_off,
            "HDMI_1": lambda: self._device.send_raw(const.CMD_SET_INPUT.format(code="32")),
            "HDMI_2": lambda: self._device.send_raw(const.CMD_SET_INPUT.format(code="33")),
            "AV_MUTE_ON": lambda: self._device.set_av_mute(True),
            "AV_MUTE_OFF": lambda: self._device.set_av_mute(False),
            "AV_MUTE_TOGGLE": self._device.toggle_av_mute,
        }
        action = actions.get(command) or actions.get(command.upper())
        if not action:
            return StatusCodes.NOT_IMPLEMENTED
        ok = await action()
        return StatusCodes.OK if ok else StatusCodes.SERVER_ERROR


def _repeat_delay(params: dict[str, Any]) -> tuple[int, float]:
    """Repeat count (at least 1) and delay in seconds from the command parameters."""
    try:
        repeat = max(1, int(params.get("repeat") or 1))
    except (TypeError, ValueError):
        repeat = 1
    try:
        delay = max(0, int(params.get("delay") or 0)) / 1000
    except (TypeError, ValueError):
        delay = 0.0
    return repeat, delay


def create_remote(device_config: EpsonConfig, device: EpsonDevice) -> list[EpsonRemote]:
    return [EpsonRemote(device_config, device)]
