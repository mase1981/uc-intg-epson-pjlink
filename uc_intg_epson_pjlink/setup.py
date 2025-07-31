# uc_intg_epson_pj/setup.py

import logging
import re
from ipaddress import ip_address
from ucapi import (
    AbortDriverSetup,
    DriverSetupRequest,
    RequestUserInput,
    SetupAction,
    SetupComplete,
    SetupDriver,
    SetupError,
    UserDataResponse,
    IntegrationSetupError,
)

try:
    from . import config
    from .config import EpsonDevice
except ImportError:
    import config
    from config import EpsonDevice

_LOGGER = logging.getLogger(__name__)

_user_input_manual = RequestUserInput(
    {"en": "Epson Projector Setup"},
    [
        {
            "id": "info",
            "label": {"en": "Manual Setup"},
            "field": {
                "label": {
                    "value": {
                        "en": "Please provide a name and the IP address for your Epson Projector."
                    }
                }
            },
        },
        {
            "field": {"text": {"value": ""}},
            "id": "name",
            "label": {"en": "Projector Name"},
        },
        {
            "field": {"text": {"value": ""}},
            "id": "ip",
            "label": {"en": "IP Address"},
        },
        {
            "field": {"password": {"value": ""}},
            "id": "password",
            "label": {"en": "PJLink Password (Optional)"},
        },
    ],
)

async def driver_setup_handler(msg: SetupDriver) -> SetupAction:
    if isinstance(msg, DriverSetupRequest):
        config.devices.clear()
        return _user_input_manual
        
    if isinstance(msg, UserDataResponse):
        return await _handle_creation(msg)
        
    if isinstance(msg, AbortDriverSetup):
        _LOGGER.info("Setup was aborted.")

    return SetupError()

async def _handle_creation(msg: UserDataResponse) -> SetupComplete | SetupError:
    ip = msg.input_values.get("ip")
    name = msg.input_values.get("name")
    password = msg.input_values.get("password", "")

    if not all([ip, name]):
        return SetupError(IntegrationSetupError.INVALID_INPUT)

    try:
        ip_address(ip)
    except ValueError:
        return SetupError(IntegrationSetupError.INVALID_INPUT)

    identifier = re.sub(r'\s+', '-', name).lower()
    identifier = re.sub(r'[^a-zA-Z0-9-]', '', identifier)

    device = EpsonDevice(
        identifier=identifier,
        name=name,
        address=ip,
        password=password,
    )

    config.devices.add_or_update(device)
    return SetupComplete()