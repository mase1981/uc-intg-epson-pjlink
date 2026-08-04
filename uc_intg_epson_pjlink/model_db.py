"""Epson model detection.

Maps a PJLink product/name string (``%1INF2`` / ``%1NAME``) to a friendly model
and a capability profile. Ported from the projector_pilot model database:
regex families + a US/EU chassis alias table + a light-source classification.

The profile is intentionally coarse: exact per-input and per-feature support is
discovered at runtime (PJLink ``INST`` for the source list, Web Control probing
for picture features). The profile mainly drives labelling and whether it is
worth attempting the richer Web Control feature set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

LIGHT_LASER = "laser"
LIGHT_LAMP = "lamp"

TIER_FLAGSHIP = "flagship"      # full picture/lens control (LS/QB series)
TIER_HOME = "home"             # consumer home cinema (EH-TW)
TIER_BUSINESS = "business"     # installation / business
TIER_LEGACY = "legacy"         # old serial-home / EMP
TIER_UNKNOWN = "unknown"


@dataclass(frozen=True)
class ModelProfile:
    """Coarse capability profile for a detected Epson model."""

    key: str
    display_name: str
    light_source: str = LIGHT_LAMP
    tier: str = TIER_UNKNOWN
    web_features_likely: bool = True

    @property
    def is_laser(self) -> bool:
        return self.light_source == LIGHT_LASER

    @property
    def light_source_label(self) -> str:
        return "Light Source" if self.is_laser else "Lamp"


# US (Home Cinema / PowerLite) -> EU (EH-TW / EB) chassis aliases.
_US_EU_ALIASES = {
    "5050UB": "EH-TW9400",
    "5050UBE": "EH-TW9400",
    "6050UB": "EH-TW9400",
    "4010": "EH-TW7400",
    "HC4010": "EH-TW7400",
    "4000": "EH-TW7300",
    "5040UB": "EH-TW8300",
    "5040UBE": "EH-TW8300",
    "3800": "EH-TW7100",
    "3700": "EH-TW7000",
    "3200": "EH-TW650",
}

_LASER_FLAGSHIP = re.compile(r"(QB1000|QL3000|LS12000|LS11000|LS800|LS500|LS300|LS650)")
_LASER_EH = re.compile(r"EH-?(LS|QB|QL)")
_HOME_EH_TW = re.compile(r"EH-?TW\d{3,4}")
_HOME_PL_HC = re.compile(r"(HOMECINEMA|HC)\d{3,4}")
_BUSINESS_LASER = re.compile(r"(EB-?[LP]|POWERLITE\s?L|PRO\s?L|EB-?PU|EB-?PQ)")
_BUSINESS_LAMP = re.compile(r"(EB-?[0-9]|EB-?FH|POWERLITE\s?[0-9]|BRIGHTLINK)")
_LEGACY = re.compile(r"(EMP[A-Z]|POWERLITEHOME|POWERLITEPC|EHTW\d{3}$)")


def _normalise(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


def detect(product: str, name: str = "") -> ModelProfile:
    """Detect an Epson model profile from product / name strings.

    ``product`` is ``%1INF2`` (e.g. ``EPSON QB1000B/QB1000W``); ``name`` is
    ``%1NAME`` (e.g. ``EPSON.QB1000``).
    """
    combined = f"{product} {name}"
    norm = _normalise(combined)

    for us, eu in _US_EU_ALIASES.items():
        if _normalise(us) in norm:
            return _profile_for(eu, eu)

    m = _LASER_FLAGSHIP.search(norm)
    if m:
        key = m.group(1)
        return ModelProfile(key=key, display_name=_pretty(product, key),
                            light_source=LIGHT_LASER, tier=TIER_FLAGSHIP)
    if _LASER_EH.search(norm):
        return ModelProfile(key="epson-laser", display_name=_pretty(product, "Laser Projector"),
                            light_source=LIGHT_LASER, tier=TIER_FLAGSHIP)
    if _HOME_EH_TW.search(norm) or _HOME_PL_HC.search(norm):
        return ModelProfile(key="epson-home", display_name=_pretty(product, "Home Cinema"),
                            light_source=LIGHT_LAMP, tier=TIER_HOME)
    if _BUSINESS_LASER.search(norm):
        return ModelProfile(key="epson-business-laser", display_name=_pretty(product, "Business Laser"),
                            light_source=LIGHT_LASER, tier=TIER_BUSINESS)
    if _BUSINESS_LAMP.search(norm):
        return ModelProfile(key="epson-business", display_name=_pretty(product, "Business Projector"),
                            light_source=LIGHT_LAMP, tier=TIER_BUSINESS)
    if _LEGACY.search(norm):
        return ModelProfile(key="epson-legacy", display_name=_pretty(product, "Projector"),
                            light_source=LIGHT_LAMP, tier=TIER_LEGACY, web_features_likely=False)

    return ModelProfile(key="epson-generic", display_name=_pretty(product, "Projector"),
                        light_source=LIGHT_LAMP, tier=TIER_UNKNOWN)


def _profile_for(key: str, product: str) -> ModelProfile:
    laser = bool(re.search(r"(LS|QB|QL)", key.upper()))
    return ModelProfile(
        key=key,
        display_name=_pretty(product, key),
        light_source=LIGHT_LASER if laser else LIGHT_LAMP,
        tier=TIER_FLAGSHIP if laser else TIER_HOME,
    )


def _pretty(product: str, fallback: str) -> str:
    """Human-friendly model name from the raw ``%1INF2`` string."""
    if not product:
        return f"Epson {fallback}"
    cleaned = product.strip()
    if cleaned.upper().startswith("EPSON"):
        cleaned = cleaned[5:].strip()
    cleaned = cleaned.split("/")[0].strip()  # QB1000B/QB1000W -> QB1000B
    return f"Epson {cleaned}" if cleaned else f"Epson {fallback}"
