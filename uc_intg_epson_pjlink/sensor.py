"""Epson projector sensors - lamp/filter hours, model, serial, input, status."""

from __future__ import annotations

import logging

from ucapi import sensor
from ucapi_framework import SensorEntity

from uc_intg_epson_pjlink.config import EpsonConfig
from uc_intg_epson_pjlink.device import EpsonDevice

_LOG = logging.getLogger(__name__)


class _BaseSensor(SensorEntity):
    """A read-only text/number sensor backed by a device accessor."""

    _sub_id = "sensor"
    _label = "Sensor"

    def __init__(self, device_config: EpsonConfig, device: EpsonDevice) -> None:
        self._device = device
        entity_id = f"sensor.{device_config.identifier}.{self._sub_id}"
        super().__init__(
            entity_id,
            f"{device_config.name} {self._label}",
            [],
            {sensor.Attributes.STATE: sensor.States.UNKNOWN, sensor.Attributes.VALUE: ""},
            device_class=sensor.DeviceClasses.CUSTOM,
        )
        self.subscribe_to_device(device)

    def _value(self) -> str:
        raise NotImplementedError

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({sensor.Attributes.STATE: sensor.States.UNAVAILABLE})
            return
        self.update({sensor.Attributes.STATE: sensor.States.ON, sensor.Attributes.VALUE: self._value()})


class LightSourceHoursSensor(_BaseSensor):
    _sub_id = "lamp_hours"

    def __init__(self, device_config: EpsonConfig, device: EpsonDevice) -> None:
        self._label = f"{device.light_source_label} Hours"
        super().__init__(device_config, device)

    def _value(self) -> str:
        hours = self._device.lamp_hours
        return f"{hours} h" if hours is not None else "N/A"


class ModelSensor(_BaseSensor):
    _sub_id = "model"
    _label = "Model"

    def _value(self) -> str:
        return self._device.model or "Unknown"


class SerialSensor(_BaseSensor):
    _sub_id = "serial"
    _label = "Serial Number"

    def _value(self) -> str:
        return self._device.serial or "Unknown"


class FirmwareSensor(_BaseSensor):
    _sub_id = "firmware"
    _label = "Firmware"

    def _value(self) -> str:
        return self._device.sw_version or "Unknown"


class InputSensor(_BaseSensor):
    _sub_id = "input"
    _label = "Input"

    def _value(self) -> str:
        return self._device.source or "None"


class StatusSensor(_BaseSensor):
    _sub_id = "status"
    _label = "Status"

    async def sync_state(self) -> None:
        if not self._device.available:
            self.update({sensor.Attributes.STATE: sensor.States.ON, sensor.Attributes.VALUE: "Unavailable"})
            return
        self.update({sensor.Attributes.STATE: sensor.States.ON, sensor.Attributes.VALUE: self._device.error_summary})


def create_sensors(device_config: EpsonConfig, device: EpsonDevice) -> list[SensorEntity]:
    return [
        LightSourceHoursSensor(device_config, device),
        ModelSensor(device_config, device),
        SerialSensor(device_config, device),
        FirmwareSensor(device_config, device),
        InputSensor(device_config, device),
        StatusSensor(device_config, device),
    ]
