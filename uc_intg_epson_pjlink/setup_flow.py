"""Setup flow for the Epson projector integration.

Validates PJLink connectivity at setup time (so the user learns immediately if
the projector is unreachable or the password is wrong) and auto-detects the
model / serial / firmware from the projector itself.
"""

from __future__ import annotations

import logging
from typing import Any

from ucapi import IntegrationSetupError, RequestUserInput, SetupError
from ucapi_framework import BaseSetupFlow

from uc_intg_epson_pjlink import const, model_db
from uc_intg_epson_pjlink.config import EpsonConfig, sanitize_identifier
from uc_intg_epson_pjlink.pjlink import PJLinkAuthError, PJLinkClient

_LOG = logging.getLogger(__name__)


class EpsonSetupFlow(BaseSetupFlow[EpsonConfig]):
    """Collect projector details, validate PJLink, and add the device."""

    def get_manual_entry_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "Epson Projector Setup"},
            [
                {
                    "id": "info",
                    "label": {"en": "Before you begin"},
                    "field": {"label": {"value": {"en": (
                        "Enter the projector's IP address (use a static IP or DHCP "
                        "reservation). PJLink must be enabled on the projector.\n\n"
                        "For power-on while the projector is in standby, set the "
                        "projector's Standby/Network setting to 'Communication On'.\n\n"
                        "The Web Control password is optional and unlocks colour-mode "
                        "control. A MAC address is optional and enables Wake-on-LAN."
                    )}}},
                },
                {"id": "name", "label": {"en": "Projector Name"},
                 "field": {"text": {"value": "Epson Projector"}}},
                {"id": "host", "label": {"en": "IP Address"},
                 "field": {"text": {"value": ""}}},
                {"id": "pjlink_port", "label": {"en": "PJLink Port"},
                 "field": {"number": {"value": const.PJLINK_PORT, "min": 1, "max": 65535}}},
                {"id": "pjlink_password", "label": {"en": "PJLink Password (optional)"},
                 "field": {"password": {"value": ""}}},
                {"id": "web_password", "label": {"en": "Web Control Password (optional)"},
                 "field": {"password": {"value": ""}}},
                {"id": "mac", "label": {"en": "MAC Address for Wake-on-LAN (optional)"},
                 "field": {"text": {"value": ""}}},
            ],
        )

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> EpsonConfig | SetupError | RequestUserInput:
        name = (input_values.get("name") or "").strip() or "Epson Projector"
        host = (input_values.get("host") or "").strip()
        if not host:
            return SetupError(error_type=IntegrationSetupError.NOT_FOUND)

        try:
            port = int(input_values.get("pjlink_port", const.PJLINK_PORT))
        except (TypeError, ValueError):
            port = const.PJLINK_PORT
        pjlink_password = (input_values.get("pjlink_password") or "").strip()
        web_password = (input_values.get("web_password") or "").strip()
        mac = (input_values.get("mac") or "").strip()

        _LOG.info("Validating PJLink connectivity to %s:%d", host, port)
        client = PJLinkClient(host, port, pjlink_password)
        try:
            if not await client.test():
                return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)
            identity = await client.get_identity()
        except PJLinkAuthError:
            _LOG.error("PJLink authentication failed for %s", host)
            return SetupError(error_type=IntegrationSetupError.AUTHORIZATION_ERROR)
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.error("PJLink connection to %s:%d failed: %s", host, port, err)
            return SetupError(error_type=IntegrationSetupError.CONNECTION_REFUSED)

        profile = model_db.detect(identity.product, identity.name)
        _LOG.info("Detected %s (serial %s)", profile.display_name, identity.serial or "unknown")

        return EpsonConfig(
            identifier=sanitize_identifier(name),
            name=name,
            host=host,
            pjlink_port=port,
            pjlink_password=pjlink_password,
            web_password=web_password,
            use_web_control=bool(web_password),
            mac=mac,
            model=profile.display_name,
            model_key=profile.key,
            serial=identity.serial,
            sw_version=identity.sw_version,
        )
