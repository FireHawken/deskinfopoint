# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Python app for a Raspberry Pi Zero 2 W that displays sensor data and Home Assistant MQTT values on a Pimoroni Display HAT Mini (320×240 ST7789). Hardware: Adafruit SCD-30 CO2/temp/humidity sensor, 4 buttons (A/B/X/Y), RGB LED.

## Setup (Raspberry Pi)

```bash
# Prerequisites: enable SPI and I2C via raspi-config; install system packages first
sudo apt install python3-pil python3-spidev python3-rpi.gpio fonts-dejavu-core libfreetype6 libjpeg62-turbo

# Create venv with system site-packages (required for GPIO/SPI access)
python3 -m venv --system-site-packages .venv
source .venv/bin/activate

pip install -e .

cp config.example.yaml config.yaml
# Edit config.yaml with your MQTT broker, topics, screens, and button mappings
```

## Commands

```bash
# Run the app
python -m deskinfopoint
python -m deskinfopoint --config /path/to/config.yaml --log-level DEBUG

# After pip install -e .
deskinfopoint --config config.yaml

# Lint
ruff check src/

# Tests (when added)
pytest
pytest tests/test_alerts.py  # run a single test file
```

## Architecture

```
src/deskinfopoint/
├── __main__.py         CLI entry point, argument parsing
├── app.py              Orchestrator: wires all subsystems, owns startup/shutdown lifecycle
├── config.py           YAML → dataclasses; _parse_condition() splits "op value" at load time
├── state.py            SharedState — single Lock, all inter-thread data flows through here
├── alerts.py           AlertEvaluator — evaluates alert configs against state, no eval()
├── mqtt_client.py      paho-mqtt 2.x wrapper (CallbackAPIVersion.VERSION2)
├── sensors/
│   └── scd30.py        SCD-30 polling thread; uses adafruit-circuitpython-scd30 + blinka
├── hardware/
│   ├── display.py      Render loop thread — calls screen.render(), pushes PIL image to display
│   ├── led.py          LED animation thread (solid/pulse/blink at 20 Hz)
│   └── buttons.py      GPIO button callbacks → state navigation or MQTT publish
└── screens/
    ├── base.py         Screen ABC, font loading (lru_cache), shared drawing helpers
    ├── sensor_screen.py  Renders SCD-30 readings; CO2 is colour-coded by threshold
    └── mqtt_screen.py    Renders MQTT subscription values; labels/units from subscription config
```

### Threading model

| Thread | Reads | Writes |
|---|---|---|
| `render` | `state.get_current_screen()`, screen render | display hardware |
| `scd30` | I2C sensor | `state.update_sensor()` |
| `led` | `state.get_sensor()`, `state.get_all_mqtt()` | LED hardware |
| `paho-network` (internal) | MQTT socket | `state.update_mqtt()` |
| `GPIO-event` (internal) | GPIO pins | `state.next/prev_screen()`, MQTT publish queue |

All state mutations go through `SharedState._lock`. The main thread blocks on `shutdown_event.wait()` and joins all threads in reverse startup order on SIGINT/SIGTERM.

### Configuration

Everything is driven by `config.yaml`. Key sections:
- `subscriptions` — MQTT topics with `id`, `topic`, `label`, `unit`, optional `value_path` (dot-notation into JSON payload)
- `screens` — ordered list; `type: sensor` uses SCD-30 fields (`co2`, `temperature`, `humidity`); `type: mqtt` references subscription ids
- `buttons` — map `A/B/X/Y` to `prev_screen`, `next_screen`, or `mqtt_publish`
- `alerts` — evaluated highest `priority` first; `condition` format: `"> 1000"`, `"== 'ON'"` etc.; `mode`: `solid`, `pulse`, `blink`

### Display library

`displayhatmini-lite` — PIL-based, no NumPy. Key methods:
- `display.display(pil_image)` — push 320×240 RGB PIL Image
- `display.set_led(r, g, b)` — 0.0–1.0 floats, active-low (handled by library)
- `display.set_backlight(brightness)` — 0.0–1.0
- `display.on_button_pressed(callback)` — single callback for all 4 buttons, fires on press and release; check `display.read_button(pin)` inside callback to filter press-only
