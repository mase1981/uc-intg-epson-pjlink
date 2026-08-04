"""Shared constants for the Epson projector integration.

Command strings, enum maps and state constants for PJLink (Class 1/2), Epson
Web Control and ESC/VP.net. Codes verified against a real Epson QB1000
(``%1INF2=EPSON QB1000B/QB1000W``, ``%1INST=32 33``).
"""

from __future__ import annotations

# -- Transport ports ---------------------------------------------------------
PJLINK_PORT = 4352
ESCVPNET_PORT = 3629
WEB_CONTROL_PORT = 80

# -- Device state strings (framework-recognised) -----------------------------
STATE_ON = "ON"
STATE_OFF = "OFF"
STATE_STANDBY = "STANDBY"
STATE_WARMING = "WARMING"
STATE_COOLING = "COOLING"
STATE_UNAVAILABLE = "UNAVAILABLE"

# -- PJLink commands ---------------------------------------------------------
CMD_POWER_ON = "%1POWR 1"
CMD_POWER_OFF = "%1POWR 0"
CMD_GET_POWER = "%1POWR ?"
CMD_GET_INPUT = "%1INPT ?"
CMD_SET_INPUT = "%1INPT {code}"
CMD_GET_INPUT_LIST = "%1INST ?"
CMD_GET_AVMUTE = "%1AVMT ?"
CMD_SET_AVMUTE_ON = "%1AVMT 31"
CMD_SET_AVMUTE_OFF = "%1AVMT 30"
CMD_GET_LAMP = "%1LAMP ?"
CMD_GET_ERRORS = "%1ERST ?"
CMD_GET_NAME = "%1NAME ?"
CMD_GET_MANUFACTURER = "%1INF1 ?"
CMD_GET_PRODUCT = "%1INF2 ?"
CMD_GET_OTHER_INFO = "%1INFO ?"
CMD_GET_CLASS = "%2CLSS ?"
CMD_GET_SERIAL = "%2SNUM ?"
CMD_GET_SW_VERSION = "%2SVER ?"
CMD_GET_REC_RESOLUTION = "%2RRES ?"
CMD_GET_FILTER_MODEL = "%2RFIL ?"
CMD_GET_FILTER_USAGE = "%2FILT ?"

# PJLink power reply codes (from ``%1POWR ?`` / ``%1POWR=<n>``)
PJLINK_POWER = {
    "0": STATE_OFF,       # standby
    "1": STATE_ON,        # lamp on
    "2": STATE_COOLING,   # cooling down
    "3": STATE_WARMING,   # warm-up
}

# PJLink AV-mute reply codes (``%1AVMT=<n>``): 30 off, 11/21/31 muted
AVMUTE_MUTED = {"11", "21", "31"}

# PJLink error-status positions for ``%1ERST=<6 chars>``
ERST_COMPONENTS = ("Fan", "Lamp", "Temperature", "Cover", "Filter", "Other")
ERST_LEVELS = {"0": "OK", "1": "Warning", "2": "Error"}

# PJLink input-code -> friendly name. INST reports which exist per device;
# type digit: 1=RGB 2=Video 3=Digital 4=Storage 5=Network.
PJLINK_INPUT_NAMES = {
    "11": "Computer 1",
    "12": "Computer 2",
    "13": "Computer",
    "21": "Video",
    "22": "S-Video",
    "23": "Component",
    "31": "HDMI",
    "32": "HDMI 1",
    "33": "HDMI 2",
    "34": "HDMI 3",
    "35": "HDMI 4",
    "41": "USB",
    "51": "LAN",
    "52": "Screen Mirroring",
    "53": "LAN",
    "56": "Wireless",
    "80": "HDBaseT",
}
PJLINK_INPUT_NAMES_INV = {v: k for k, v in PJLINK_INPUT_NAMES.items()}

# -- Epson Web Control (HTTP) color/picture modes ----------------------------
# CMODE reply code -> display name. Superset from projector_pilot + HA.
WEB_COLOR_MODES = {
    "00": "Auto",
    "01": "Photo",
    "05": "Theatre",
    "06": "Dynamic",
    "07": "Natural",
    "09": "Theatre Black 1",
    "0A": "Theatre Black 2",
    "0B": "x.v. Color",
    "0C": "Bright Cinema",
    "0D": "Game",
    "11": "Presentation",
    "13": "THX",
    "15": "Cinema",
    "16": "Stage",
    "17": "3D Cinema",
    "18": "3D Dynamic",
    "19": "3D THX",
    "20": "B&W Cinema",
    "21": "Adobe RGB",
    "22": "Digital Cinema",
    "23": "Vivid",
    "C1": "AutoColor",
}
WEB_COLOR_MODES_INV = {v: k for k, v in WEB_COLOR_MODES.items()}

# Epson Web Control aspect reply code -> name
WEB_ASPECT_MODES = {
    "00": "Auto",
    "10": "4:3",
    "20": "16:9",
    "30": "Full",
    "40": "Zoom",
    "50": "Native",
    "60": "Anamorphic",
    "70": "H-Squeeze",
}

# Default Web Control digest username
WEB_USERNAME = "EPSONWEB"

# -- ESC/VP21 command set (shared by ESC/VP.net TCP and Web Control HTTP) -----
# Power reply codes for "PWR?" -> "PWR=<code>"
ESCVP_POWER = {
    "00": STATE_OFF,       # standby, network off
    "01": STATE_ON,        # lamp on
    "02": STATE_WARMING,   # warm-up
    "03": STATE_COOLING,   # cool-down
    "04": STATE_OFF,       # standby, network on
    "05": STATE_OFF,       # abnormal standby
    "09": STATE_OFF,       # A/V standby
}

# ESC/VP21 source reply code -> friendly name (verified codes from Epson docs
# and projector_pilot). Set with "SOURCE <code>".
ESCVP_SOURCE_NAMES = {
    "10": "Computer 1",
    "20": "Computer 2",
    "30": "HDMI 1",
    "40": "Video",
    "41": "S-Video",
    "42": "Component",
    "52": "USB",
    "53": "LAN",
    "56": "Screen Mirroring",
    "80": "HDBaseT",
    "A0": "HDMI 2",
    "B0": "SDI",
    "D0": "WirelessHD",
}
ESCVP_SOURCE_NAMES_INV = {v: k for k, v in ESCVP_SOURCE_NAMES.items()}
