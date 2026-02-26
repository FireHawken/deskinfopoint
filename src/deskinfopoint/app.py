from __future__ import annotations

import logging
import signal
import threading

from displayhatmini_lite import DisplayHATMini  # type: ignore[import-untyped]

from .alerts import AlertEvaluator
from .config import AppConfig, ScreenConfig, SubscriptionConfig
from .hardware.buttons import ButtonHandler
from .hardware.display import DisplayController
from .hardware.led import LEDController
from .mqtt_client import MQTTClient
from .screens.base import Screen
from .screens.brightness_screen import BrightnessScreen
from .screens.mqtt_screen import MQTTScreen
from .screens.sensor_screen import SensorScreen
from .sensors.scd30 import SCD30Sensor
from .state import SharedState

logger = logging.getLogger(__name__)


def _build_screens(
    screen_configs: list[ScreenConfig],
    subs_by_id: dict[str, SubscriptionConfig],
) -> list[Screen]:
    screens: list[Screen] = []
    for cfg in screen_configs:
        if cfg.type == "sensor":
            screens.append(SensorScreen(cfg))
        elif cfg.type == "mqtt":
            screens.append(MQTTScreen(cfg, subs_by_id))
        elif cfg.type == "brightness":
            screens.append(BrightnessScreen(cfg.name))
        else:
            logger.warning("Unknown screen type %r — skipped", cfg.type)
    return screens


class App:
    """Wires all subsystems together and owns the application lifecycle."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._shutdown = threading.Event()

        subs_by_id = {s.id: s for s in config.subscriptions}
        screens = _build_screens(config.screens, subs_by_id)
        if not screens:
            raise RuntimeError("No valid screens were built from configuration")

        self._state = SharedState(
            screen_count=len(screens),
            initial_brightness=config.display.brightness,
        )

        self._display_hw = DisplayHATMini(backlight_pwm=config.display.backlight_pwm)
        self._display_hw.set_backlight(config.display.brightness)

        self._mqtt = MQTTClient(config.mqtt, config.subscriptions, self._state)
        self._sensor = SCD30Sensor(config.sensor, self._state, self._shutdown)

        evaluator = AlertEvaluator(config.alerts, self._state)
        self._led = LEDController(
            self._display_hw, evaluator, config.led_idle, self._shutdown
        )
        self._renderer = DisplayController(
            self._display_hw, screens, self._state, config.display.fps, self._shutdown
        )
        self._buttons = ButtonHandler(
            self._display_hw, config.buttons, self._state, self._mqtt,
            self._shutdown, screens,
        )

    def run(self) -> None:
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        logger.info("Starting deskinfopoint")
        self._mqtt.start()
        self._sensor.start()
        self._led.start()
        self._renderer.start()
        self._buttons.start()

        self._shutdown.wait()  # main thread blocks here until signal

        logger.info("Shutdown: stopping subsystems")
        self._buttons.join()
        self._renderer.join()
        self._led.join()
        self._sensor.join()
        self._mqtt.stop()
        self._display_hw.set_led(0.0, 0.0, 0.0)
        self._display_hw.set_backlight(0.0)
        logger.info("Shutdown complete")

    def _handle_signal(self, signum: int, frame: object) -> None:
        logger.info("Received signal %d", signum)
        self._shutdown.set()
