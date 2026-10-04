"""Setup flow for the Epson projector integration.

Lets the user pick the control protocol (Auto / PJLink / ESC/VP.net / Web
Control) and best-effort probes the projector to auto-detect the model. An
unreachable projector never blocks setup - the device connects and fills in the
model at runtime. A rejected password, a missing IP or a bad MAC is shown on the
form with the typed values kept. Running setup again (Update) starts from the
saved values and keeps the projector's ID, so entities and activities stay intact.
"""

from __future__ import annotations

import logging
from typing import Any

from ucapi import RequestUserInput, SetupError
from ucapi_framework import BaseSetupFlow

from uc_intg_epson import model_db, transport, wol
from uc_intg_epson.config import EpsonConfig, sanitize_identifier
from uc_intg_epson.const import PJLINK_PORT
from uc_intg_epson.transport import ProjectorIdentity, TransportAuthError

_LOG = logging.getLogger(__name__)


class EpsonSetupFlow(BaseSetupFlow[EpsonConfig]):
    """Collect projector details, probe the chosen protocol, and add the device."""

    def get_manual_entry_form(self, error: str = "", values: dict[str, Any] | None = None) -> RequestUserInput:
        saved = self.selected_config_entry
        values = values or {}

        def pick(key: str, default: Any) -> Any:
            if values.get(key) not in (None, ""):
                return values[key]
            return getattr(saved, key, default) if saved else default

        keep = " (leave empty to keep the saved one)" if saved else " (optional)"
        problem = [{
            "id": "error",
            "label": {"en": "Problem"},
            "field": {"label": {"value": {"en": error}}},
        }] if error else []
        return RequestUserInput(
            {"en": "Epson Projector Setup"},
            problem + [
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
                 "field": {"text": {"value": pick("name", "Epson Projector")}}},
                {"id": "host", "label": {"en": "IP Address"},
                 "field": {"text": {"value": pick("host", "")}}},
                {
                    "id": "protocol",
                    "label": {"en": "Control Protocol"},
                    "field": {"dropdown": {
                        "value": pick("protocol", transport.PROTOCOL_AUTO),
                        "items": [
                            {"id": transport.PROTOCOL_AUTO, "label": {"en": "Auto-detect (recommended)"}},
                            {"id": transport.PROTOCOL_PJLINK, "label": {"en": "PJLink (port 4352)"}},
                            {"id": transport.PROTOCOL_ESCVPNET, "label": {"en": "ESC/VP.net (port 3629)"}},
                            {"id": transport.PROTOCOL_WEBCONTROL, "label": {"en": "Web Control (HTTP)"}},
                        ],
                    }},
                },
                {"id": "pjlink_port", "label": {"en": "PJLink Port"},
                 "field": {"number": {"value": int(pick("pjlink_port", PJLINK_PORT)), "min": 1, "max": 65535}}},
                {"id": "pjlink_password", "label": {"en": "PJLink Password" + keep},
                 "field": {"password": {"value": ""}}},
                {"id": "web_password", "label": {"en": "Web Control / ESC-VP Password" + keep},
                 "field": {"password": {"value": ""}}},
                {"id": "mac", "label": {"en": "MAC Address for Wake-on-LAN (optional)"},
                 "field": {"text": {"value": pick("mac", "")}}},
            ],
        )

    async def query_device(
        self, input_values: dict[str, Any]
    ) -> EpsonConfig | SetupError | RequestUserInput:
        saved = self.selected_config_entry
        name = (input_values.get("name") or "").strip() or "Epson Projector"
        host = "".join(str(input_values.get("host") or "").split())
        host = host.split("://")[-1].split("/")[0]
        values = {**input_values, "name": name, "host": host}
        if not host:
            return self.get_manual_entry_form("Enter the projector's IP address.", values)

        protocol = (input_values.get("protocol") or transport.PROTOCOL_AUTO).strip()
        if protocol not in transport.PROTOCOLS:
            protocol = transport.PROTOCOL_AUTO
        try:
            port = int(float(input_values.get("pjlink_port") or PJLINK_PORT))
        except (TypeError, ValueError):
            port = PJLINK_PORT
        # Empty password fields keep the saved ones when updating.
        pjlink_password = (input_values.get("pjlink_password") or "").strip() or (
            saved.pjlink_password if saved else ""
        )
        web_password = (input_values.get("web_password") or "").strip() or (
            saved.web_password if saved else ""
        )
        mac = (input_values.get("mac") or "").strip()
        if mac and not wol.normalise_mac(mac):
            return self.get_manual_entry_form(
                "The MAC address looks wrong. Use the format AA:BB:CC:DD:EE:FF, or leave it empty.", values
            )

        # Updating keeps the projector's ID so entities and activities stay intact.
        identifier = saved.identifier if saved else sanitize_identifier(name)
        if not saved and self.config.contains(identifier):
            return self.get_manual_entry_form(
                f"A projector named '{name}' is already set up. Choose a different name.", values
            )

        config = EpsonConfig(
            identifier=identifier,
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
        identity, detected, auth_failed = await self._probe(config)
        if detected:
            profile = model_db.detect(identity.product, identity.name)
            config.model = profile.display_name
            config.model_key = profile.key
            config.serial = identity.serial
            config.sw_version = identity.sw_version
            config.protocol = detected  # lock onto the transport that answered
            _LOG.info("Detected %s via %s (serial %s)",
                      profile.display_name, detected, identity.serial or "unknown")
        elif auth_failed:
            # The projector answered but refused the password: it would never work.
            return self.get_manual_entry_form(
                f"The projector answered on {', '.join(auth_failed)} but refused the password. "
                "Check the password (as set in the projector's network settings).",
                values,
            )
        else:
            _LOG.info("Projector %s not reachable now; will connect when available", host)
            if saved:
                # Keep what was learned before (model, serial) when the projector is off.
                config.model, config.model_key = saved.model, saved.model_key
                config.serial, config.sw_version = saved.serial, saved.sw_version
        return config

    async def _probe(self, config: EpsonConfig) -> tuple[ProjectorIdentity, str, list[str]]:
        """Try each candidate transport: (identity, protocol answering, protocols refusing the password)."""
        auth_failed: list[str] = []
        for candidate in transport.build_candidates(config):
            try:
                if await candidate.probe():
                    identity = await candidate.get_identity()
                    await candidate.close()
                    return identity, candidate.name, auth_failed
                await candidate.close()
            except TransportAuthError:
                _LOG.warning("%s refused the password for %s", candidate.name, config.host)
                auth_failed.append(candidate.name)
                await candidate.close()
            except Exception as err:  # pylint: disable=broad-exception-caught
                _LOG.debug("%s probe failed for %s: %s", candidate.name, config.host, err)
                try:
                    await candidate.close()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
        return ProjectorIdentity(), "", auth_failed
