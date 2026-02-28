# deskinfopoint

A small Python app for a DIY desk info display built on a Raspberry Pi Zero 2 W. Displays local air quality sensor readings and Home Assistant MQTT data on a Pimoroni Display HAT Mini. Buttons on the HAT can switch screens and send MQTT commands to Home Assistant.

## Hardware

- Raspberry Pi Zero 2 W
- [Pimoroni Display HAT Mini](https://shop.pimoroni.com/products/display-hat-mini) — 320×240 IPS display, 4 buttons (A/B/X/Y), RGB LED
- Adafruit SCD-30 CO2/temperature/humidity sensor (I2C)

## Setup

### 1. Enable interfaces

```bash
sudo raspi-config nonint do_spi 0    # enable SPI (display)
sudo raspi-config nonint do_i2c 0    # enable I2C (SCD-30 sensor)
```

### 2. Install system packages

Do this **before** creating the virtual environment so PIL/freetype are available:

```bash
sudo apt install python3-pil python3-spidev python3-rpi.gpio \
                 fonts-dejavu-core libfreetype6 libjpeg62-turbo zlib1g
```

### 3. Create virtual environment and install

The venv must use `--system-site-packages` so GPIO and SPI drivers are accessible:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -e .
```

### 4. Configure

```bash
cp config.example.yaml config.yaml
# Edit config.yaml — set your MQTT broker, topics, screens, button mappings, and LED alerts
```

## Running manually

```bash
source .venv/bin/activate
python -m deskinfopoint
# or after pip install -e .:
deskinfopoint

# with options:
python -m deskinfopoint --config /path/to/config.yaml --log-level DEBUG
```

## Auto-start on boot (systemd)

Run the install script once to register and enable a systemd service:

```bash
bash install-service.sh
```

The script creates `/etc/systemd/system/deskinfopoint.service`, enables it, and starts it immediately. The service starts automatically after every reboot, restarts on failure, and waits for the network to be available before launching.

Useful commands:

```bash
sudo systemctl status deskinfopoint      # check status
sudo journalctl -u deskinfopoint -f      # follow live logs
sudo systemctl restart deskinfopoint     # restart manually
sudo systemctl disable deskinfopoint     # remove from autostart
```

## Configuration

All behaviour is controlled by `config.yaml`. See `config.example.yaml` for a fully annotated example. Key sections:

| Section | What it controls |
|---|---|
| `mqtt` | Broker address, credentials |
| `ha` | *(optional)* Home Assistant URL and Long-Lived Access Token for startup prefetch |
| `subscriptions` | MQTT topics to subscribe to, with label, unit, optional JSON `value_path`, and optional `entity_id` for HA prefetch |
| `screens` | Ordered list of screens; `type: sensor` shows SCD-30 data, `type: mqtt` shows subscription values |
| `buttons` | Map A/B/X/Y to `prev_screen`, `next_screen`, or `mqtt_publish` |
| `alerts` | LED colour/mode when thresholds are crossed (e.g. CO2 > 1000 ppm) |
| `led_idle` | LED colour when no alert is active |

### LED alert modes

| Mode | Behaviour |
|---|---|
| `solid` | Constant colour |
| `pulse` | Smooth sine-wave brightness cycle |
| `blink` | On/off at configurable Hz |

## Notes

- Buttons use polling (not GPIO interrupts) due to a kernel 6.x incompatibility with RPi.GPIO edge detection.
- SCD-30 CO2 readings colour-code automatically: green < 800 ppm → yellow → orange → red ≥ 1500 ppm.
- MQTT values referencing an undefined subscription will display a red error tile on screen.
