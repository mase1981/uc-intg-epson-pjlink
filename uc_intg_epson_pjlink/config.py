"""Configuration dataclass, manager and legacy migration for Epson projectors."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass

from ucapi_framework import BaseConfigManager

from uc_intg_epson_pjlink import const

_LOG = logging.getLogger(__name__)


@dataclass
class EpsonConfig:
    """Configuration for a single Epson projector."""

    identifier: str = ""
    name: str = ""
    host: str = ""
    pjlink_port: int = const.PJLINK_PORT
    pjlink_password: str = ""
    web_password: str = ""      # Web Control (EPSONWEB) password; enables picture control
    use_web_control: bool = False
    mac: str = ""               # optional, for Wake-on-LAN power-on from deep standby
    model: str = ""             # detected friendly model name
    model_key: str = ""         # matched model-profile key
    serial: str = ""
    sw_version: str = ""


class EpsonConfigManager(BaseConfigManager[EpsonConfig]):
    """Config manager bound to :class:`EpsonConfig`."""


def sanitize_identifier(value: str) -> str:
    """Slug safe for entity IDs (no dots - the framework splits IDs on '.')."""
    slug = re.sub(r"\s+", "-", (value or "").strip()).lower()
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug.strip("-") or "projector"


def migrate_legacy_config(config_path: str) -> None:
    """Rewrite a pre-1.1 config.json in place to the new schema.

    The original integration stored ``{identifier, name, address, password}``.
    We preserve ``identifier`` (so entity IDs and activities stay intact) and
    map ``address`` -> ``host`` and ``password`` -> ``pjlink_password``. Runs
    once; a config already in the new schema (``host`` present) is left alone.
    """
    cfg_file = os.path.join(config_path, "config.json")
    if not os.path.exists(cfg_file):
        return
    try:
        with open(cfg_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as err:
        _LOG.warning("Could not read config for migration: %s", err)
        return

    if not isinstance(data, list):
        return

    defaults = asdict(EpsonConfig())
    allowed = set(defaults.keys())
    changed = False
    for item in data:
        if not isinstance(item, dict):
            continue
        if "address" in item and "host" not in item:
            item["host"] = item.pop("address")
            changed = True
        if "password" in item and "pjlink_password" not in item:
            item["pjlink_password"] = item.pop("password")
            changed = True
        # Drop unknown keys, then backfill any missing ones so EpsonConfig(**item) is safe.
        for key in list(item.keys()):
            if key not in allowed:
                item.pop(key)
                changed = True
        for fname, default in defaults.items():
            if fname not in item:
                item[fname] = default
                changed = True

    if changed:
        try:
            with open(cfg_file, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            _LOG.info("Migrated legacy Epson config to new schema (%d device(s))", len(data))
        except OSError as err:
            _LOG.error("Could not write migrated config: %s", err)
