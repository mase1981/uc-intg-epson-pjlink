import asyncio
import logging
import hashlib
from enum import IntEnum, StrEnum
from asyncio import AbstractEventLoop
from pyee.asyncio import AsyncIOEventEmitter
from config import EpsonDevice
import const

_LOGGER = logging.getLogger(__name__)
PORT = 4352

class EVENTS(IntEnum):
    UPDATE = 1

class PowerState(StrEnum):
    OFF = "OFF"
    ON = "ON"
    STANDBY = "STANDBY"
    UNKNOWN = "UNKNOWN"

class EpsonProjector:
    def __init__(self, device_config: EpsonDevice, loop: AbstractEventLoop | None = None):
        self._loop: AbstractEventLoop = loop or asyncio.get_running_loop()
        self.events = AsyncIOEventEmitter(self._loop)
        self._device_config = device_config
        self._state: PowerState = PowerState.UNKNOWN
        self._is_polling = False
        self._lock = asyncio.Lock()

    @property
    def identifier(self) -> str: return self._device_config.identifier
    @property
    def name(self) -> str: return self._device_config.name
    @property
    def state(self) -> PowerState: return self._state

    async def start_polling(self):
        if self._is_polling: return
        self._is_polling = True
        self._loop.create_task(self._poll_loop())

    async def stop_polling(self):
        self._is_polling = False

    async def _poll_loop(self):
        while self._is_polling:
            await self.update()
            await asyncio.sleep(15)

    async def update(self):
        power_status_raw = await self._get_power_status()
        new_state = PowerState.ON if power_status_raw == 'on' else PowerState.STANDBY
        if self._state != new_state:
            self._state = new_state
            self.events.emit(EVENTS.UPDATE, self.identifier, {"state": self._state})

    async def set_power(self, state: str):
        command = const.POWER_ON if state == 'on' else const.POWER_OFF
        await self._send_command(command)

    async def send_raw_command(self, command: str):
        await self._send_command(command)

    async def _get_power_status(self) -> str:
        response = await self._send_command(const.GET_POWER)
        return 'on' if response and "POWR=1" in response else 'off'
        
    async def _send_command(self, command: str) -> str | None:
        async with self._lock:
            reader, writer = None, None
            try:
                host = self._device_config.address
                password = self._device_config.password if self._device_config.password else ""
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, PORT), timeout=3.0
                )
                initial_response = (await reader.read(100)).decode('utf-8')
                if "PJLINK 1" in initial_response:
                    nonce = initial_response.split(' ')[1].strip()
                    auth_hash = hashlib.md5((password + nonce).encode('utf-8')).hexdigest()
                    writer.write(auth_hash.encode('utf-8'))
                    await writer.drain()
                    full_command = f"{auth_hash}{command}\r"
                else:
                    full_command = f"{command}\r"
                writer.write(full_command.encode('utf-8'))
                await writer.drain()
                response_data = await asyncio.wait_for(reader.read(100), timeout=3.0)
                decoded_response = response_data.decode('utf-8').strip()
                _LOGGER.debug(f"[{self.name}] Sent '{command}', Received '{decoded_response}'")
                return decoded_response
            except Exception as e:
                _LOGGER.error(f"[{self.name}] PJLink communication error on command '{command}': {e}")
                return None
            finally:
                if writer:
                    writer.close()
                    await writer.wait_closed()