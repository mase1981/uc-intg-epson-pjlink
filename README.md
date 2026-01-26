# Epson Projector (PJLink) Integration for Unfolded Circle Remote 2/3

Control your network-connected Epson projectors directly from your Unfolded Circle Remote 2 or Remote 3 using the PJLink protocol with **IP control**, **power management**, and **input switching**.

![Epson](https://img.shields.io/badge/Epson-Projector-blue)
[![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-epson-pjlink?style=flat-square)](https://github.com/mase1981/uc-intg-epson-pjlink/releases)
![License](https://img.shields.io/badge/license-MPL--2.0-blue?style=flat-square)
[![GitHub issues](https://img.shields.io/github/issues/mase1981/uc-intg-epson-pjlink?style=flat-square)](https://github.com/mase1981/uc-intg-epson-pjlink/issues)
[![Community Forum](https://img.shields.io/badge/community-forum-blue?style=flat-square)](https://community.unfoldedcircle.com/)
[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/mase1981/uc-intg-epson-pjlink/total?style=flat-square)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=flat-square)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg?style=flat-square)](https://paypal.me/mmiyara)
[![Github Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&logoColor=EA4AAA&style=flat-square)](https://github.com/sponsors/mase1981)


## Features

This integration provides IP control of network-connected Epson projectors using the PJLink protocol, delivering direct control without IR emitters.

---
## ❤️ Support Development ❤️

If you find this integration useful, consider supporting development:

[![GitHub Sponsors](https://img.shields.io/badge/Sponsor-GitHub-pink?style=for-the-badge&logo=github)](https://github.com/sponsors/mase1981)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white)](https://paypal.me/mmiyara)

Your support helps maintain this integration. Thank you! ❤️
---

### 🎥 **Projector Control**

#### **Power Management**
- **Power On/Off** - Turn projector on and off (standby)
- **State Feedback** - Real-time power state monitoring
- **State Polling** - Periodic status checks for UI updates

#### **Input Switching**
- **HDMI 1** - Direct selection of HDMI input 1
- **HDMI 2** - Direct selection of HDMI input 2
- **Quick Switching** - Fast input changes via custom UI

#### **Network Control**
- **IP Control** - No IR emitters required
- **PJLink Protocol** - Standard projector control protocol
- **Password Support** - Supports PJLink password authentication
- **Persistent Configuration** - Remembers settings between restarts

### 🎮 **Entities**

This integration creates two distinct entities:

#### **MediaPlayer Entity**
- Used to determine projector state
- Provides status information
- Updates automatically with state changes

#### **Remote Entity**
- Custom UI with control buttons
- Direct control of power and inputs
- Optimized button layout

### **Protocol Requirements**

- **Protocol**: PJLink
- **Network Access**: Projector must be on same local network
- **IP Address**: Static IP or DHCP reservation recommended
- **Password**: Optional PJLink password support

### **Network Requirements**

- **Local Network Access** - Integration requires same network as projector
- **IP Control** - Direct network communication via PJLink
- **Static IP Recommended** - Projector should have static IP or DHCP reservation

## Installation

### Option 1: Remote Web Interface (Recommended)
1. Navigate to the [**Releases**](https://github.com/mase1981/uc-intg-epson-pjlink/releases) page
2. Download the latest `uc-intg-epson-pjlink-<version>-aarch64.tar.gz` file
3. Open your remote's web interface (`http://your-remote-ip`)
4. Go to **Settings** → **Integrations** → **Add Integration**
5. Click **Upload** and select the downloaded `.tar.gz` file

### Option 2: Docker (Advanced Users)

The integration is available as a pre-built Docker image:

**Docker Compose:**
```yaml
services:
  uc-intg-epson-pjlink:
    image: mase1981/uc-intg-epson-pjlink:latest
    container_name: uc-intg-epson-pjlink
    network_mode: host
    volumes:
      - </local/path>:/data
    environment:
      - UC_CONFIG_HOME=/data
      - UC_INTEGRATION_HTTP_PORT=9090
      - UC_INTEGRATION_INTERFACE=0.0.0.0
      - PYTHONPATH=/app
    restart: unless-stopped
```

**Docker Run:**
```bash
docker run -d --name uc-epson-pjlink --restart unless-stopped --network host -v epson-config:/app/config -e UC_CONFIG_HOME=/app/config -e UC_INTEGRATION_INTERFACE=0.0.0.0 -e UC_INTEGRATION_HTTP_PORT=9090 -e PYTHONPATH=/app mase1981/uc-intg-epson-pjlink:latest
```

## Configuration

### Step 1: Prepare Your Epson Projector

**IMPORTANT**: Projector must be powered on and connected to your network before adding the integration.

#### Verify Network Connection:
1. Check that projector is connected to network (Ethernet or Wi-Fi)
2. Note the IP address from projector's network settings
3. Ensure PJLink is enabled (usually enabled by default)
4. Note the PJLink password if configured (optional)

#### Network Setup:
- **Wired Connection**: Recommended for stability
- **Static IP**: Recommended via DHCP reservation
- **Network Isolation**: Must be on same subnet as Remote
- **PJLink Access**: Ensure PJLink is not blocked by projector settings

### Step 2: Setup Integration

1. After installation, go to **Settings** → **Integrations**
2. The Epson Projector (PJLink) integration should appear in **Available Integrations**
3. Click **"Configure"** to begin setup:

#### **Configuration:**
- **Name**: Friendly name for the projector (e.g., "Living Room Projector")
- **IP Address**: Enter projector IP (e.g., 192.168.1.100)
- **Password**: PJLink password (leave blank if not set)
- Click **Complete Setup**

4. Integration will create **two entities**:
   - **[Projector Name]** - MediaPlayer entity for status
   - **[Projector Name] Remote** - Remote entity with control buttons

## Using the Integration

### Remote Entity

Add the **Remote** entity to your UI for complete control:

- **Power Controls**: Turn On, Turn Off buttons
- **Input Controls**: HDMI 1, HDMI 2 direct selection
- **Custom UI Pages**: Organized control layout
- **Visual Feedback**: Button states reflect projector status

### MediaPlayer Entity

The MediaPlayer entity provides:

- **Status Monitoring**: Current projector state
- **Activity Integration**: Use in UC activities for automation
- **State Feedback**: Real-time power and input status

**Important Note**: Add the **Remote** entity to your UI. The MediaPlayer is primarily for status and activities.

## Credits

- **Developer**: Meir Miyara
- **Unfolded Circle**: Remote 2/3 integration framework (ucapi)
- **PJLink Protocol**: Standard projector control protocol
- **Community**: Testing and feedback from UC community
- **Inspiration**: Jack Powell (uc-intg-jvc), kennymc-c (ucr2-integration-requests)

## License

This project is licensed under the Mozilla Public License 2.0 (MPL-2.0) - see LICENSE file for details.

## Support & Community

- **GitHub Issues**: [Report bugs and request features](https://github.com/mase1981/uc-intg-epson-pjlink/issues)
- **UC Community Forum**: [General discussion and support](https://community.unfoldedcircle.com/)
- **Developer**: [Meir Miyara](https://www.linkedin.com/in/meirmiyara)

---

**Made with ❤️ for the Unfolded Circle Community**

**Thank You**: Meir Miyara
