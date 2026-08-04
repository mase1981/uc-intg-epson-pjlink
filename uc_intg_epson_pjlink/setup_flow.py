"""Setup flow for the Epson projector integration.

Lets the user pick the control protocol (Auto / PJLink / ESC/VP.net / Web
Control) and best-effort probes the projector to auto-detect the model. An
unreachable projector never blocks setup - the device connects and fills in the
model at runtime.
"""

from __future__ import annotations

import logging
from typing import Any

from ucapi import IntegrationSetupError, RequestUserInput, SetupError
from ucapi_framework import BaseSetupFlow

from uc_intg_epson_pjlink import model_db, transport
from uc_intg_epson_pjlink.config import EpsonConfig, sanitize_identifier
from uc_intg_epson_pjlink.const import PJLINK_PORT
from uc_intg_epson_pjlink.transport import ProjectorIdentity, TransportAuthError

_LOG = logging.getLogger(__name__)


class EpsonSetupFlow(BaseSetupFlow[EpsonConfig]):
    """Collect projector details, probe the chosen protocol, and add the device."""

    def get_manual_entry_form(self) -> RequestUserInput:
        return RequestUserInput(
            {"en": "Epson Projector Setup"},
            [
                {
                    "id": "info",
                    "label": {"en": "Before you begin"},
                    "field": {"label": {"value": {"en": (
                        "Enter the projector's IP address (use a static IP or DHCP "
                        "reservation).\n\n"
                        "Control protocol: choose Auto to detect it automatically. "
                        "Business/large-venue models usually use PJLink (port 4352); "
                        "consumer home-cinema models often use ESC/VP.net (3629) or "
                        "Web Control (HTTP). Make sure network control is enabled on "
                        "the projector.\n\n"
                        "The Web Control password is optional (needed if the projector "
                        "has one set, and unlocks colour-mode control). A MAC address "
                        "is optional and enables Wake-on-LAN."
                    )}}},
                },
                {"id": "name", "label": {"en": "Projector Name"},
                 "field": {"text": {"value": "Epson Projector"}}},
                {"id": "host", "label": {"en": "IP Address"},
                 "field": {"text": {"value": ""}}},
                {
                    "id": "protocol",
                    "label": {"en": "Control Protocol"},
                    "field": {"dropdown": {
                        "value": transport.PROTOCOL_AUTO,
                        "items": [
                            {"id": transport.PROTOCOL_AUTO, "label": {"en": "Auto-detect (recommended)"}},
                            {"id": transport.PROTOCOL_PJLINK, "label": {"en": "PJLink (port 4352)"}},
                            {"id": transport.PROTOCOL_ESCVPNET, "label": {"en": "ESC/VP.net (port 3629)"}},
                            {"id": transport.PROTOCOL_WEBCONTROL, "label": {"en": "Web Control (HTTP)"}},
                        ],
                    }},
                },
                {"id": "pjlink_port", "label": {"en": "PJLink Port"},
                 "field": {"number": {"value": PJLINK_PORT, "min": 1, "max": 65535}}},
                {"id": "pjlink_password", "label": {"en": "PJLink Password (optional)"},
                 "field": {"password": {"value": ""}}},
                {"id": "web_password", "label": {"en": "Web Control / ESC-VP Password (optional)"},
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

        protocol = (input_values.get("protocol") or transport.PROTOCOL_AUTO).strip()
        if protocol not in transport.PROTOCOLS:
            protocol = transport.PROTOCOL_AUTO
        try:
            port = int(input_values.get("pjlink_port", PJLINK_PORT))
        except (TypeError, ValueError):
            port = PJLINK_PORT
        pjlink_password = (input_values.get("pjlink_password") or "").strip()
        web_password = (input_values.get("web_password") or "").strip()
        mac = (input_values.get("mac") or "").strip()

        config = EpsonConfig(
            identifier=sanitize_identifier(name),
            name=name,
            host=host,
            protocol=protocol,
            pjlink_port=port,
            pjlink_password=pjlink_password,
            web_password=web_password,
            use_web_control=bool(web_password),
            mac=mac,
        )

        # Best-effort probe of the selected protocol(s). An unreachable projector
        # must NOT block setup - the device connects and fills in the model later.
        identity, detected = await self._probe(config)
        if detected:
            profile = model_db.detect(identity.product, identity.name)
            config.model = profile.display_name
            config.model_key = profile.key
            config.serial = identity.serial
            config.sw_version = identity.sw_version
            config.protocol = detected  # lock onto the transport that answered
            _LOG.info("Detected %s via %s (serial %s)",
                      profile.display_name, detected, identity.serial or "unknown")
        else:
            _LOG.info("Projector %s not reachable now; will connect when available", host)
        return config

    async def _probe(self, config: EpsonConfig) -> tuple[ProjectorIdentity, str]:
        """Try each candidate transport; return (identity, protocol_name) or empty."""
        for candidate in transport.build_candidates(config):
            try:
                if await candidate.probe():
                    identity = await candidate.get_identity()
                    await candidate.close()
                    return identity, candidate.name
                await candidate.close()
            except TransportAuthError:
                _LOG.warning("%s needs a password for %s; completing anyway",
                             candidate.name, config.host)
                await candidate.close()
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.debug("%s probe failed for %s: %s", candidate.name, config.host, err)
                try:
                    await candidate.close()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
        return ProjectorIdentity(), ""
