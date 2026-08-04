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
from uc_intg_epson_pjlink.pjlink import PJLinkAuthError, PJLinkClient, PJLinkIdentity

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

        # Best-effort probe: if the projector answers we auto-detect the model,
        # but an unreachable projector (off, networked standby with
        # "Communication Off", warming up, etc.) must NOT block setup. The
        # device layer handles reconnection at runtime and fills in the model
        # on the first successful connect.
        _LOG.info("Probing PJLink at %s:%d", host, port)
        identity = PJLinkIdentity()
        reachable = False
        client = PJLinkClient(host, port, pjlink_password)
        try:
            if await client.test():
                identity = await client.get_identity()
                reachable = True
        except PJLinkAuthError:
            _LOG.warning("PJLink auth failed for %s; completing setup anyway", host)
        except Exception as err:  # pylint: disable=broad-exception-caught
            _LOG.warning("Projector %s not reachable at setup (%s); completing anyway", host, err)

        if reachable:
            profile = model_db.detect(identity.product, identity.name)
            _LOG.info("Detected %s (serial %s)", profile.display_name, identity.serial or "unknown")
        else:
            profile = None
            _LOG.info("Projector %s not reachable now; will connect when available", host)

        return EpsonConfig(
            identifier=sanitize_identifier(name),
            name=name,
            host=host,
            pjlink_port=port,
            pjlink_password=pjlink_password,
            web_password=web_password,
            use_web_control=bool(web_password),
            mac=mac,
            model=profile.display_name if profile else "",
            model_key=profile.key if profile else "",
            serial=identity.serial,
            sw_version=identity.sw_version,
        )
