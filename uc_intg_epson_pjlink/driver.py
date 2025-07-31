# uc_intg_epson_pj/driver.py

import asyncio
import logging
import os
import sys
from typing import Any

import ucapi
from ucapi import media_player, remote, EntityTypes

# This try/except block allows the code to run both locally (as a package)
# and on the remote (as a flat directory).
try:
    from . import config, setup, const
    from .remote import EpsonMediaPlayer, EpsonRemote
    from .config import EpsonDevice, create_entity_id, device_from_entity_id
    from .projector import EpsonProjector, EVENTS, PowerState
except ImportError:
    import config
    import setup
    import const
    from remote import EpsonMediaPlayer, EpsonRemote
    from config import EpsonDevice, create_entity_id, device_from_entity_id
    from projector import EpsonProjector, EVENTS, PowerState

_LOG = logging.getLogger("driver")
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)

api = ucapi.IntegrationAPI(_LOOP)
_configured_devices: dict[str, EpsonProjector] = {}

@api.listens_to(ucapi.Events.CONNECT)
async def on_connect() -> None:
    """Handle the connect event from the remote."""
    _LOG.info("Connection received, setting device state to CONNECTED.")
    await api.set_device_state(ucapi.DeviceStates.CONNECTED)

@api.listens_to(ucapi.Events.SUBSCRIBE_ENTITIES)
async def on_subscribe_entities(entity_ids: list[str]) -> None:
    """Handle the subscribe_entities event from the remote."""
    _LOG.debug("Subscribed to entities: %s", entity_ids)
    for entity_id in entity_ids:
        device_id = device_from_entity_id(entity_id)
        if device_id and device_id in _configured_devices:
            device = _configured_devices[device_id]
            
            state = _device_state_to_media_player_state(device.state)
            remote_state = _device_state_to_remote_state(device.state)

            if entity_id.startswith("media_player"):
                 api.configured_entities.update_attributes(entity_id, {media_player.Attributes.STATE: state})
            elif entity_id.startswith("remote"):
                 api.configured_entities.update_attributes(entity_id, {remote.Attributes.STATE: remote_state})

def _device_state_to_media_player_state(dev_state: PowerState) -> media_player.States:
    if dev_state == PowerState.ON: return media_player.States.ON
    return media_player.States.STANDBY

def _device_state_to_remote_state(dev_state: PowerState) -> remote.States:
    if dev_state == PowerState.ON: return remote.States.ON
    return remote.States.OFF

async def on_device_update(identifier: str, update: dict[str, Any] | None) -> None:
    media_player_id = create_entity_id(identifier, EntityTypes.MEDIA_PLAYER)
    remote_id = create_entity_id(identifier, EntityTypes.REMOTE)
    
    mp_attributes = {}
    remote_attributes = {}

    if "state" in update:
        mp_state = _device_state_to_media_player_state(update["state"])
        remote_state = _device_state_to_remote_state(update["state"])
        mp_attributes[media_player.Attributes.STATE] = mp_state
        remote_attributes[remote.Attributes.STATE] = remote_state

    if mp_attributes and api.configured_entities.contains(media_player_id):
        api.configured_entities.update_attributes(media_player_id, mp_attributes)
    if remote_attributes and api.configured_entities.contains(remote_id):
        api.configured_entities.update_attributes(remote_id, remote_attributes)

def _add_configured_device(device_config: EpsonDevice) -> None:
    if device_config.identifier in _configured_devices:
        return

    _LOG.info(f"Adding new device: {device_config.name} ({device_config.address})")
    device = EpsonProjector(device_config, loop=_LOOP)
    device.events.on(EVENTS.UPDATE, on_device_update)
    _configured_devices[device.identifier] = device

    entities = [
        EpsonMediaPlayer(device_config, device),
        EpsonRemote(device_config, device)
    ]
    for entity in entities:
        if not api.available_entities.contains(entity.id):
            api.available_entities.add(entity)
    
    _LOOP.create_task(device.start_polling())

def on_device_added(device: EpsonDevice) -> None:
    _add_configured_device(device)

def on_device_removed(device: EpsonDevice | None) -> None:
    if device is None:
        for dev in _configured_devices.values():
            _LOOP.create_task(dev.stop_polling())
        _configured_devices.clear()
        api.available_entities.clear()
        api.configured_entities.clear()
    else:
        if device.identifier in _configured_devices:
            _LOG.info(f"Removing device: {device.name}")
            dev_instance = _configured_devices.pop(device.identifier)
            _LOOP.create_task(dev_instance.stop_polling())
            mp_id = create_entity_id(device.identifier, EntityTypes.MEDIA_PLAYER)
            remote_id = create_entity_id(device.identifier, EntityTypes.REMOTE)
            api.available_entities.remove(mp_id)
            api.configured_entities.remove(mp_id)
            api.available_entities.remove(remote_id)
            api.configured_entities.remove(remote_id)

async def main():
    logging.basicConfig()
    level = os.getenv("UC_LOG_LEVEL", "DEBUG").upper()
    logging.getLogger("uc_intg_epson_pjlink").setLevel(level)
    
    config.devices = config.Devices(
        api.config_dir_path, on_device_added, on_device_removed
    )

    for device_config in config.devices.all():
        _add_configured_device(device_config)

    await api.init("driver.json", setup.driver_setup_handler)

if __name__ == "__main__":
    _LOOP.run_until_complete(main())
    _LOOP.run_forever()