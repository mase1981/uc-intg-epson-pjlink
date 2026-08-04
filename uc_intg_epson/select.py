"""Epson projector Select entities - input source and (optional) colour mode."""

from __future__ import annotations

import logging
from typing import Any

from ucapi import StatusCodes, select
from ucapi_framework import SelectEntity

from uc_intg_epson.config import EpsonConfig
from uc_intg_epson.device import EpsonDevice

_LOG = logging.getLogger(__name__)


class EpsonSourceSelect(SelectEntity):
    """Selects the active input on the projector."""

    def __init__(self, device_config: EpsonConfig, device: EpsonDevice) -> None:
        self._device = device
        entity_id = f"select.{device_config.identifier}.source"
        super().__init__(
            entity_id,
            f"{device_config.name} Source",
            {
                select.Attributes.STATE: select.States.UNKNOWN,
                select.Attributes.OPTIONS: [],
                select.Attributes.CURRENT_OPTION: "",
            },
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({select.Attributes.STATE: select.States.UNAVAILABLE})
            return
        self.update({
            select.Attributes.STATE: select.States.ON,
            select.Attributes.OPTIONS: self._device.source_list,
            select.Attributes.CURRENT_OPTION: self._device.source,
        })

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict | None = None, *_a: Any
    ) -> StatusCodes:
        if cmd_id != select.Commands.SELECT_OPTION:
            return StatusCodes.NOT_IMPLEMENTED
        option = (params or {}).get("option", "")
        if not option:
            return StatusCodes.BAD_REQUEST
        return StatusCodes.OK if await self._device.select_source(option) else StatusCodes.BAD_REQUEST


class EpsonColorModeSelect(SelectEntity):
    """Selects the colour/picture mode via Web Control (optional)."""

    def __init__(self, device_config: EpsonConfig, device: EpsonDevice) -> None:
        self._device = device
        entity_id = f"select.{device_config.identifier}.color_mode"
        super().__init__(
            entity_id,
            f"{device_config.name} Color Mode",
            {
                select.Attributes.STATE: select.States.UNKNOWN,
                select.Attributes.OPTIONS: [],
                select.Attributes.CURRENT_OPTION: "",
            },
            cmd_handler=self._handle_command,
        )
        self.subscribe_to_device(device)

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({select.Attributes.STATE: select.States.UNAVAILABLE})
            return
        self.update({
            select.Attributes.STATE: select.States.ON,
            select.Attributes.OPTIONS: self._device.color_mode_list,
            select.Attributes.CURRENT_OPTION: self._device.color_mode or "",
        })

    async def _handle_command(
        self, entity: Any, cmd_id: str, params: dict | None = None, *_a: Any
    ) -> StatusCodes:
        if cmd_id != select.Commands.SELECT_OPTION:
            return StatusCodes.NOT_IMPLEMENTED
        option = (params or {}).get("option", "")
        if not option:
            return StatusCodes.BAD_REQUEST
        return StatusCodes.OK if await self._device.set_color_mode(option) else StatusCodes.BAD_REQUEST


def create_selects(device_config: EpsonConfig, device: EpsonDevice) -> list[SelectEntity]:
    selects: list[SelectEntity] = [EpsonSourceSelect(device_config, device)]
    if device_config.use_web_control:
        selects.append(EpsonColorModeSelect(device_config, device))
    return selects
