# Epson Projector Integration for Unfolded Circle Remote 2/3

Control your **network-connected Epson projectors** directly from your Unfolded Circle Remote 2 or Remote 3. Power, input/source switching, AV-mute, colour mode, Wake-on-LAN, and rich status sensors (model, serial, firmware, lamp/light-source hours, error status) - all over the local network. Supports **PJLink** (TCP 4352), Epson's native **ESC/VP.net** (TCP 3629), and **Epson Web Control** (HTTP), auto-detected or chosen at setup. No IR emitters required.

![Epson](https://img.shields.io/badge/Epson-Projector-blue)
[![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-epson-pjlink?style=flat-square)](https://github.com/mase1981/uc-intg-epson-pjlink/releases)
![License](https://img.shields.io/badge/license-MPL--2.0-blue?style=flat-square)
[![GitHub issues](https://img.shields.io/github/issues/mase1981/uc-intg-epson-pjlink?style=flat-square)](https://github.com/mase1981/uc-intg-epson-pjlink/issues)
[![Community Forum](https://img.shields.io/badge/community-forum-blue?style=flat-square)](https://unfolded.community/)
[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/mase1981/uc-intg-epson-pjlink/total?style=flat-square)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg?style=flat-square)](https://paypal.me/mmiyara)
[![Github Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&logoColor=EA4AAA&style=flat-square)](https://github.com/sponsors/mase1981)

## Supported Devices

Network-connected Epson projectors, including the **Home Cinema / EH-TW** series, the **LS / QB laser** flagships (e.g. LS12000, QB1000), and **EB / PowerLite** business projectors. The integration speaks three protocols and picks whichever the projector supports:

- **PJLink** (TCP 4352) - common on business/large-venue models and many home models.
- **ESC/VP.net** (TCP 3629) - Epson's native protocol; used by consumer home-cinema models that don't expose PJLink.
- **Web Control** (HTTP) - the Epson web interface; also usable for control.

The projector must have **network control enabled** and be reachable on the LAN. Model, serial and firmware are auto-detected where the protocol provides them.

## Features

- **🎥 Full media player** - power on/off/toggle, current input + selectable source list, and AV-mute (mute/unmute/toggle), with warm-up and cool-down state feedback.
- **🔀 Source switching** - the input list is built automatically from the projector's own reported inputs (PJLink `INST`).
- **🎛️ Remote entity** - a ready-made button page (power, HDMI 1/2, AV-mute) plus power/input simple commands for Activities. Accepts raw PJLink commands via `send_cmd`.
- **🎨 Colour mode** - pick the picture preset (Cinema, Natural, Dynamic, …) via Web Control (added only when a Web Control password is provided).
- **📊 Status sensors** - Lamp / Light-Source Hours, Model, Serial Number, Firmware, Input, and Status (error summary).
- **⏰ Wake-on-LAN** - optional magic-packet wake so the projector can be powered on from deep standby.
- **🔀 Multiple protocols** - PJLink, ESC/VP.net, or Web Control, with an **Auto-detect** option that probes and locks onto whichever the projector answers.
- **🔎 Automatic model detection** - laser models are labelled "Light Source Hours", lamp models "Lamp Hours".
- **Multi-device** - add each projector on your network.

---
## ❤️ Support Development ❤️

If you find this integration useful, consider supporting development:

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge&logo=github)](https://github.com/sponsors/mase1981)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/mmiyara)

Your support helps maintain this integration. Thank you! ❤️
---

## How It Works

Control is **fully local** over the projector's network connection:

- **PJLink** (TCP 4352) is the mandatory transport - power, inputs, AV-mute, lamp/filter hours, device identity and error status.
- **Epson Web Control** (HTTP) is an optional, password-gated enhancement that adds colour-mode control and a standby power-on path for models that keep HTTP alive while PJLink is closed.
- For power-on while the projector is in standby, set the projector's Standby/Network setting to **"Communication On"** so the network stays reachable. If your model closes the network in standby, provide the projector's **MAC address** to enable Wake-on-LAN.

## Requirements

- An Epson projector with **PJLink enabled**, on the same network as your Remote.
- A **static IP** or DHCP reservation for the projector (strongly recommended).
- (Optional) the **PJLink password** and/or **Web Control password** if configured on the projector.
- Unfolded Circle Remote 2 / 3 with firmware supporting custom integrations.

## Installation

### Option 1: Remote Web Interface (Recommended)

1. Download the latest `uc-intg-epson-pjlink-<version>-aarch64.tar.gz` from the [**Releases**](https://github.com/mase1981/uc-intg-epson-pjlink/releases) page.
2. Open your Remote's web interface (`http://your-remote-ip`).
3. Go to **Settings -> Integrations -> Add Integration -> Install Custom** and upload the `.tar.gz`.

### Option 2: Docker (Advanced Users)

**Image**: `ghcr.io/mase1981/uc-intg-epson-pjlink:latest`

**Docker Compose:**
```yaml
services:
  uc-intg-epson-pjlink:
    image: ghcr.io/mase1981/uc-intg-epson-pjlink:latest
    container_name: uc-intg-epson-pjlink
    network_mode: host
    volumes:
      - ./config:/config
    environment:
      - UC_CONFIG_HOME=/config
      - UC_INTEGRATION_HTTP_PORT=9090
      - UC_INTEGRATION_INTERFACE=0.0.0.0
    restart: unless-stopped
```

**Docker Run:**
```bash
docker run -d --name uc-intg-epson-pjlink --restart unless-stopped --network host -v $(pwd)/config:/config -e UC_CONFIG_HOME=/config -e UC_INTEGRATION_INTERFACE=0.0.0.0 -e UC_INTEGRATION_HTTP_PORT=9090 ghcr.io/mase1981/uc-intg-epson-pjlink:latest
```

## Configuration

1. Start setup and enter your projector's details:
   - **Projector Name** - a friendly name (e.g. "Cinema Projector").
   - **IP Address** and **PJLink Port** (default `4352`).
   - **Control Protocol** - **Auto-detect** (recommended), or force **PJLink**, **ESC/VP.net**, or **Web Control**.
   - **PJLink Password** - optional.
   - **Web Control / ESC-VP Password** - optional; needed if the projector has a monitor/Web Control password set, and unlocks colour-mode control.
   - **MAC Address** - optional; enables Wake-on-LAN.
2. The integration probes the projector, auto-detects the model, and creates the entities. (An unreachable projector still completes setup and connects later.)
3. Repeat setup to add additional projectors.

For each projector the integration creates:

| Entity | Purpose |
|--------|---------|
| **Media player** (`<name>`) | Power, current source + source list, AV-mute. |
| **Remote** (`<name> Remote`) | Power, HDMI 1/2 and AV-mute on a button page + simple commands for Activities. |
| **Select** (`<name> Source`) | Pick the active input. |
| **Select** (`<name> Color Mode`) | Pick the picture preset (only with a Web Control password). |
| **Sensors** | Lamp / Light-Source Hours, Model, Serial Number, Firmware, Input, Status. |

> **Upgrading from v1.x?** Existing setups are migrated automatically - your projector and entity IDs are preserved, so Activities keep working. No re-pairing required.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Connection refused" / cannot connect | The projector isn't answering the chosen protocol. Leave **Control Protocol** on **Auto-detect** so it tries PJLink, ESC/VP.net, and Web Control. Ensure network control is enabled on the projector and the port isn't blocked by a VLAN/firewall (4352 PJLink, 3629 ESC/VP.net, 80 Web Control). Many Epson models close the network in standby - set Standby/Network to **"Communication On"**, and/or add the MAC address for Wake-on-LAN. |
| Works with Home Assistant but not here | HA uses ESC/VP.net or Web Control for consumer models. Set **Control Protocol** to **ESC/VP.net** (or **Auto-detect**), and enter the monitor/Web Control password if one is set. Note: models with no network port at all (e.g. some entry-level home units) can only be controlled by IR. |
| Setup fails with an authorization error | The projector has a password set - enter the PJLink or Web Control/ESC-VP password during setup. |
| Colour Mode entity missing | It is only created when a **Web Control password** is provided at setup. |
| Sensors show "N/A" while the projector is off | Some values (input, colour mode) are only available while the projector is powered on. |
| Source switch does nothing | Only inputs the projector actually reports (PJLink `INST`) are selectable. |

## Credits

- **Developer**: Meir Miyara
- **PJLink**: standard projector control protocol; Epson Web Control for extended features.
- **Unfolded Circle**: Remote 2/3 integration framework ([ucapi](https://github.com/unfoldedcircle/integration-python-library) / [ucapi-framework](https://github.com/JackJPowell/ucapi-framework)).

## License

Mozilla Public License 2.0 (MPL-2.0) - see the LICENSE file.

## Support & Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-epson-pjlink/issues)
- **UC Community Forum**: [General discussion and support](https://unfolded.community/)
- **Developer**: [Meir Miyara](https://www.linkedin.com/in/meirmiyara)

---

**Made with ❤️ for the Unfolded Circle Community**

**Thank You**: Meir Miyara
