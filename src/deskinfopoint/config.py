from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import time as Time
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Condition parsing (used by AlertConfig)
# Parses strings like "> 1000" or "== 'ON'" into (op_str, threshold).
# ---------------------------------------------------------------------------
_OP_PATTERN = re.compile(r"^(>=|<=|!=|>|<|==)\s*(.+)$")


def _parse_condition(s: str) -> tuple[str, float | str]:
    m = _OP_PATTERN.match(s.strip())
    if not m:
        raise ConfigError(f"Cannot parse condition {s!r}. Expected e.g. '> 1000' or \"== 'ON'\"")
    op, raw = m.group(1), m.group(2).strip()
    # Try numeric first
    try:
        return op, float(raw)
    except ValueError:
        pass
    # Strip surrounding quotes for string comparisons
    if len(raw) >= 2 and raw[0] in ("'", '"') and raw[-1] == raw[0]:
        return op, raw[1:-1]
    return op, raw


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class HaConfig:
    url: str     # e.g. http://homeassistant.local:8123
    token: str   # Long-Lived Access Token


@dataclass
class MqttConfig:
    broker: str
    port: int = 1883
    client_id: str = "deskinfopoint"
    username: str = ""
    password: str = ""
    keepalive: int = 60


@dataclass
class SensorConfig:
    measurement_interval: int = 5
    temperature_offset: float = 0.0
    altitude: int = 0
    publish_topic: str = ""   # MQTT topic for JSON sensor readings; empty = disabled


@dataclass
class DisplayConfig:
    brightness: float = 1.0
    fps: int = 10
    backlight_pwm: bool = False   # True requires dtoverlay=pwm-2chan in config.txt


@dataclass
class SubscriptionConfig:
    id: str
    topic: str
    label: str
    unit: str = ""
    value_path: str = ""
    entity_id: str = ""   # HA entity id for startup prefetch (e.g. sensor.lumi_temp4_temperature_2)
    value_map: dict[str, str] = field(default_factory=dict)  # map raw MQTT values to display strings


@dataclass
class SensorItem:
    label: str
    source: str   # "co2" | "temperature" | "humidity"
    unit: str = ""
    format: str = "{}"


@dataclass
class MqttItem:
    subscription_id: str
    format: str = "{}"


@dataclass
class MixedItem:
    """Item for a 'mixed' screen — either a sensor source or an MQTT subscription."""
    source: str = ""           # "co2" | "temperature" | "humidity"
    subscription_id: str = ""  # MQTT subscription id
    label: str = ""            # explicit label; MQTT items fall back to subscription label
    unit: str = ""             # explicit unit; MQTT items fall back to subscription unit
    format: str = "{}"


@dataclass
class ScreenConfig:
    name: str
    type: str   # "sensor" | "mqtt" | "mixed" | "brightness" | "led_brightness"
    items: list[SensorItem | MqttItem | MixedItem] = field(default_factory=list)


@dataclass
class ButtonConfig:
    action: str   # "prev_screen" | "next_screen" | "mqtt_publish"
    topic: str = ""
    payload: str = ""


@dataclass
class AlertConfig:
    source: str
    op: str
    threshold: float | str
    color: tuple[float, float, float]
    mode: str = "solid"   # "solid" | "blink" | "pulse"
    blink_hz: float = 2.0
    pulse_hz: float = 1.0
    priority: int = 0


@dataclass
class LedIdleConfig:
    color: tuple[float, float, float] = (0.0, 0.0, 0.0)
    mode: str = "solid"


@dataclass
class NightModeConfig:
    start: Time   # local wall-clock time sleep begins
    end: Time     # local wall-clock time sleep ends (may be next day)
    wake_duration: int = 30   # seconds display + LED stay on after a button press


@dataclass
class AppConfig:
    mqtt: MqttConfig
    sensor: SensorConfig
    display: DisplayConfig
    subscriptions: list[SubscriptionConfig]
    screens: list[ScreenConfig]
    buttons: dict[str, ButtonConfig]
    alerts: list[AlertConfig]
    led_idle: LedIdleConfig
    ha: HaConfig | None = None
    night_mode: NightModeConfig | None = None


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def _parse_time(s: str, context: str) -> Time:
    try:
        h, m = str(s).split(":")
        return Time(int(h), int(m))
    except (ValueError, AttributeError):
        raise ConfigError(f"Invalid time {s!r} in {context}; expected HH:MM")


def _require(d: dict, key: str, context: str) -> Any:
    if key not in d:
        raise ConfigError(f"Missing required key '{key}' in {context}")
    return d[key]


def _color(raw: list, context: str) -> tuple[float, float, float]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise ConfigError(f"Color in {context} must be a list of 3 floats [R, G, B]")
    return (float(raw[0]), float(raw[1]), float(raw[2]))


def load_config(path: str) -> AppConfig:
    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except FileNotFoundError:
        raise
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error in {path}: {e}") from e

    if not isinstance(raw, dict):
        raise ConfigError("Config file must be a YAML mapping")

    # --- ha (optional) ---
    ha: HaConfig | None = None
    if "ha" in raw:
        h = raw["ha"]
        ha = HaConfig(
            url=_require(h, "url", "ha").rstrip("/"),
            token=_require(h, "token", "ha"),
        )

    # --- mqtt ---
    m = raw.get("mqtt", {})
    mqtt = MqttConfig(
        broker=_require(m, "broker", "mqtt"),
        port=m.get("port", 1883),
        client_id=m.get("client_id", "deskinfopoint"),
        username=m.get("username", ""),
        password=m.get("password", ""),
        keepalive=m.get("keepalive", 60),
    )

    # --- sensor ---
    s = raw.get("sensor", {})
    sensor = SensorConfig(
        measurement_interval=s.get("measurement_interval", 5),
        temperature_offset=s.get("temperature_offset", 0.0),
        altitude=s.get("altitude", 0),
        publish_topic=s.get("publish_topic", ""),
    )

    # --- display ---
    d = raw.get("display", {})
    display = DisplayConfig(
        brightness=d.get("brightness", 1.0),
        fps=d.get("fps", 10),
        backlight_pwm=d.get("backlight_pwm", False),
    )

    # --- subscriptions ---
    subscriptions: list[SubscriptionConfig] = []
    for i, sub in enumerate(raw.get("subscriptions", [])):
        raw_map = sub.get("value_map", {})
        if not isinstance(raw_map, dict):
            raise ConfigError(f"value_map in subscriptions[{i}] must be a mapping")
        subscriptions.append(SubscriptionConfig(
            id=_require(sub, "id", f"subscriptions[{i}]"),
            topic=_require(sub, "topic", f"subscriptions[{i}]"),
            label=sub.get("label", sub["id"]),
            unit=sub.get("unit", ""),
            value_path=sub.get("value_path", ""),
            entity_id=sub.get("entity_id", ""),
            value_map={str(k): str(v) for k, v in raw_map.items()},
        ))

    # --- screens ---
    screens: list[ScreenConfig] = []
    for i, sc in enumerate(raw.get("screens", [])):
        sc_type = _require(sc, "type", f"screens[{i}]")
        items: list[SensorItem | MqttItem] = []
        for j, item in enumerate(sc.get("items", [])):
            ctx = f"screens[{i}].items[{j}]"
            if sc_type == "sensor":
                items.append(SensorItem(
                    label=_require(item, "label", ctx),
                    source=_require(item, "source", ctx),
                    unit=item.get("unit", ""),
                    format=item.get("format", "{}"),
                ))
            elif sc_type == "mqtt":
                items.append(MqttItem(
                    subscription_id=_require(item, "subscription_id", ctx),
                    format=item.get("format", "{}"),
                ))
            elif sc_type == "mixed":
                src = item.get("source", "")
                sub_id = item.get("subscription_id", "")
                if not src and not sub_id:
                    raise ConfigError(f"Item in {ctx} must have 'source' or 'subscription_id'")
                if src and sub_id:
                    raise ConfigError(f"Item in {ctx} cannot have both 'source' and 'subscription_id'")
                items.append(MixedItem(
                    source=src,
                    subscription_id=sub_id,
                    label=item.get("label", ""),
                    unit=item.get("unit", ""),
                    format=item.get("format", "{}"),
                ))
            elif sc_type in ("brightness", "led_brightness"):
                pass  # these screens take no items
            else:
                raise ConfigError(f"Unknown screen type {sc_type!r} in screens[{i}]")
        screens.append(ScreenConfig(
            name=_require(sc, "name", f"screens[{i}]"),
            type=sc_type,
            items=items,
        ))

    if not screens:
        raise ConfigError("At least one screen must be defined")

    # --- buttons ---
    buttons: dict[str, ButtonConfig] = {}
    valid_buttons = {"A", "B", "X", "Y"}
    for name, btn in raw.get("buttons", {}).items():
        if name not in valid_buttons:
            raise ConfigError(f"Invalid button name {name!r}; must be one of {valid_buttons}")
        buttons[name] = ButtonConfig(
            action=_require(btn, "action", f"buttons.{name}"),
            topic=btn.get("topic", ""),
            payload=btn.get("payload", ""),
        )

    # --- alerts ---
    alerts: list[AlertConfig] = []
    for i, al in enumerate(raw.get("alerts", [])):
        ctx = f"alerts[{i}]"
        op, threshold = _parse_condition(_require(al, "condition", ctx))
        alerts.append(AlertConfig(
            source=_require(al, "source", ctx),
            op=op,
            threshold=threshold,
            color=_color(_require(al, "color", ctx), ctx),
            mode=al.get("mode", "solid"),
            blink_hz=al.get("blink_hz", 2.0),
            pulse_hz=al.get("pulse_hz", 1.0),
            priority=al.get("priority", 0),
        ))

    # --- led_idle ---
    li = raw.get("led_idle", {})
    led_idle = LedIdleConfig(
        color=_color(li.get("color", [0.0, 0.0, 0.0]), "led_idle"),
        mode=li.get("mode", "solid"),
    )

    # --- night_mode (optional) ---
    night_mode: NightModeConfig | None = None
    if "night_mode" in raw:
        nm = raw["night_mode"]
        night_mode = NightModeConfig(
            start=_parse_time(_require(nm, "start", "night_mode"), "night_mode.start"),
            end=_parse_time(_require(nm, "end", "night_mode"), "night_mode.end"),
            wake_duration=int(nm.get("wake_duration", 30)),
        )

    return AppConfig(
        mqtt=mqtt,
        sensor=sensor,
        display=display,
        subscriptions=subscriptions,
        screens=screens,
        buttons=buttons,
        alerts=alerts,
        led_idle=led_idle,
        ha=ha,
        night_mode=night_mode,
    )
