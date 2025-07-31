# uc_intg_epson_pj/config.py

import dataclasses
import json
import logging
import os
from asyncio import Lock
from dataclasses import dataclass
from typing import Iterator

from ucapi import EntityTypes

_LOG = logging.getLogger(__name__)

def create_entity_id(device_id: str, entity_type: EntityTypes) -> str:
    """Create a unique entity identifier."""
    return f"{entity_type.value}.{device_id}"

def device_from_entity_id(entity_id: str) -> str | None:
    """Return the id prefix of an entity_id."""
    if "." in entity_id:
        return entity_id.split(".", 1)[1]
    return None

@dataclass
class EpsonDevice:
    """Epson device configuration."""
    identifier: str
    name: str
    address: str
    password: str = ""

class _EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)

class Devices:
    """Manages all configured Epson projector devices."""
    def __init__(self, data_path: str, add_handler, remove_handler):
        self._data_path: str = data_path
        self._cfg_file_path: str = os.path.join(data_path, "config.json")
        self._config: list[EpsonDevice] = []
        self._add_handler = add_handler
        self._remove_handler = remove_handler
        self.load()
        self._config_lock = Lock()

    def all(self) -> Iterator[EpsonDevice]:
        return iter(self._config)

    def add_or_update(self, device: EpsonDevice) -> None:
        if not self.update(device):
            self._config.append(device)
            self.store()
            if self._add_handler:
                self._add_handler(device)

    def get(self, device_id: str) -> EpsonDevice | None:
        for item in self._config:
            if item.identifier == device_id:
                return dataclasses.replace(item)
        return None

    def update(self, device: EpsonDevice) -> bool:
        for item in self._config:
            if item.identifier == device.identifier:
                item.address = device.address
                item.name = device.name
                item.password = device.password
                self.store()
                return True
        return False

    def remove(self, device_id: str) -> bool:
        device = self.get(device_id)
        if device is None:
            return False
        try:
            self._config.remove(device)
            if self._remove_handler:
                self._remove_handler(device)
            self.store()
            return True
        except ValueError:
            pass
        return False
    
    def clear(self) -> None:
        """Remove the configuration file."""
        self._config = []
        if os.path.exists(self._cfg_file_path):
            os.remove(self._cfg_file_path)
        if self._remove_handler:
            self._remove_handler(None)

    def store(self) -> bool:
        try:
            with open(self._cfg_file_path, "w+", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, cls=_EnhancedJSONEncoder)
            return True
        except OSError as err:
            _LOG.error("Cannot write the config file: %s", err)
        return False

    def load(self) -> bool:
        if not os.path.exists(self._cfg_file_path):
            return False
        try:
            with open(self._cfg_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                device = EpsonDevice(**item)
                self._config.append(device)
            return True
        except (OSError, json.JSONDecodeError, TypeError) as err:
            _LOG.error("Cannot open or parse the config file: %s", err)
        return False

devices: Devices | None = None