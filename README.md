# Epson Projector (PJLink) Integration for Unfolded Circle
[![Discord](https://badgen.net/discord/online-members/zGVYf58)](https://discord.gg/zGVYf58)
![GitHub Release](https://img.shields.io/github/v/release/mase1981/uc-intg-epson-pjlink)
![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/mase1981/uc-intg-epson-pjlink/total)
![License](https://img.shields.io/badge/license-MPL--2.0-blue)
[![Buy Me A Coffee](https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg)](https://buymeacoffee.com/meirmiyara)
[![PayPal](https://img.shields.io/badge/PayPal-donate-blue.svg)](https://paypal.me/mmiyara)
[![Github Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-30363D?&logo=GitHub-Sponsors&logoColor=EA4AAA)](https://github.com/sponsors/mase1981/button)

This is a custom integration for the Unfolded Circle Remote family (Remote Two and Remote 3) that allows for IP control of network-connected Epson projectors using the PJLink protocol.

This integration creates two distinct entities on your remote:
* A **MediaPlayer** entity, this is used to determine the state of the projector.
* A **Remote** entity, which provides a custom UI with buttons for direct control of power and inputs.
* **NOTE:** This integration was tested against Epson QB1000 Projector, all Epson connected projectors which support PJLink should work, however it was only tested against QB1000. 

## Features

* **IP Control:** No need for IR emitters. Control your projector directly over your local network.
* **Power Control:** Turn the projector On and Off (Standby).
* **Input Switching:** Directly select HDMI 1 and HDMI 2.
* **State Polling:** The integration periodically checks the projector's power status and updates the UI on the remote automatically.
* **Persistent Configuration:** Remembers your projector's settings between restarts.
* **Password Support:** If you have a password setup for PJLink, integration will support it. 

## Installation

### Option 1: `tar.gz` File (Recommended for most users)
1.  Navigate to the [**Releases**](https://github.com/mase1981/uc-intg-epson-pjlink/releases) page for this repository.
2.  Download the latest `uc-intg-epson-pjlink.tar.gz` file from the Assets section.
3.  Open a web browser and navigate to your Unfolded Circle remote's IP address to access the web configurator.
4.  Go to **Settings** -> **Integrations**.
5.  Click the "UPLOAD" button and select the `uc-intg-epson-pjlink.tar.gz` file you just downloaded.

### Option 2: Docker
For users running Docker (e.g., on a Synology NAS), you can deploy this integration as a container.

**Docker Compose (Recommended):**
Use the `docker-compose.yml` file in this repository. Update the `volumes` section to match a path on your host machine where you want to store the configuration file. Then run:

    docker-compose up -d

**Docker Run (Single Command for SSH):**
Replace `/path/on/your/host/config` with an actual path on your machine (e.g., `/volume1/docker/epson-pjlink/config`).

    docker run -d --restart=unless-stopped --net=host -v /path/on/your/host/config:/app/uc_intg_epson_pjlink/config --name epson-pjlink-integration mase1981/uc-intg-epson-pjlink:latest

## Configuration

1.  After installation, go to **Settings** -> **Integrations** on your remote and click **+ ADD INTEGRATION**.
2.  Select **Epson Projector (PJLink)** from the list.
3.  Follow the on-screen prompts to enter a **Name** and the **IP Address** of your projector, Password is optional.
4.  Once setup is complete, two new entities will be available to add to your remote's user interface.

> **Important Note on Entities (READ CAREFULLY):**
> * **`[Projector Name] Remote`:** Add this entity to your UI. It contains the custom pages with all the control buttons (Power, Inputs, etc.).
> * **`[Projector Name]` (MediaPlayer):** This entity is primarily for status and for use in Activities. You **do not** need to add it to your UI, as its page will be blank and pressing it may cause an error.

## For Developers

To run this integration locally for development or debugging:

1.  Clone the repository:

        git clone https://github.com/mase1981/uc-intg-epson-pjlink.git
        cd uc-intg-epson-pjlink

2.  Create and activate a Python virtual environment:

        python -m venv .venv
        # On Windows
        .venv\Scripts\activate

3.  Install the required dependencies:

        pip install -r requirements.txt

4.  Run the integration driver:

        python -m uc_intg_epson_pj.driver

The driver will now be discoverable by your Unfolded Circle remote on the local network.

## Acknowledgements

This integration was made possible by the hard work and inspiration from others in the Unfolded Circle community.

* [Jack Powell](https://github.com/JackJPowell) for the excellent [uc-intg-jvc](https://github.com/JackJPowell/uc-intg-jvc) integration, which served as the architectural model for this project.
* [kennymc-c](https://github.com/kennymc-c) for the [ucr2-integration-requests](https://github.com/kennymc-c/ucr2-integration-requests) project, which was the initial inspiration for a text-over-TCP integration.
* **The Unfolded Circle Team** for creating a fantastic product and providing the [ucapi library](https://github.com/unfoldedcircle/integration-python-library) for developers.