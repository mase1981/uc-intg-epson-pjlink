# uc_intg_epson_pj/const.py

# PJLink Standard Command Strings
# Using the correct codes from your Epson documentation.
# Note: '%1' is a placeholder for the projector body ID, which is standard.

# Power Commands
POWER_ON = "%1POWR 1"
POWER_OFF = "%1POWR 0"
GET_POWER = "%1POWR ?"

# Input Sources
INPUT_HDMI1 = "%1INPT 32"
INPUT_HDMI2 = "%1INPT 33"

# Menu Navigation (For projectors that support it)
KEY_UP = "%1RCKEY 38"
KEY_DOWN = "%1RCKEY 39"
KEY_LEFT = "%1RCKEY 3A"
KEY_RIGHT = "%1RCKEY 3B"
KEY_ENTER = "%1RCKEY 3C"
KEY_MENU = "%1RCKEY 3D"
KEY_ESC = "%1RCKEY 3E"