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
from .ha_prefetch import prefetch as ha_prefetch
from .mqtt_client import MQTTClient
from . import persistence
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

    def __init__(self, config: AppConfig, state_file: str) -> None:
        self._config = config
        self._state_file = state_file
        self._shutdown = threading.Event()

        subs_by_id = {s.id: s for s in config.subscriptions}
        screens = _build_screens(config.screens, subs_by_id)
        if not screens:
            raise RuntimeError("No valid screens were built from configuration")

        # Load persisted state; fall back to config defaults.
        saved = persistence.load(state_file)
        initial_brightness = float(saved.get("brightness", config.display.brightness))
        initial_screen = int(saved.get("screen", 0))
        # Clamp screen index in case the screen list has shrunk since last run.
        initial_screen = max(0, min(initial_screen, len(screens) - 1))

        self._state = SharedState(
            screen_count=len(screens),
            initial_brightness=initial_brightness,
        )
        # Restore saved screen position.
        for _ in range(initial_screen):
            self._state.next_screen()

        self._display_hw = DisplayHATMini(backlight_pwm=config.display.backlight_pwm)
        self._display_hw.set_backlight(initial_brightness)

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
        if self._config.ha:
            ha_prefetch(self._config.ha, self._config.subscriptions, self._state)
        self._led.start()
        self._renderer.start()
        self._buttons.start()

        # Watcher: save screen + brightness whenever either changes (≈1 Hz poll).
        watcher = threading.Thread(target=self._persist_watcher, name="persist", daemon=True)
        watcher.start()

        self._shutdown.wait()  # main thread blocks here until signal

        logger.info("Shutdown: stopping subsystems")
        self._buttons.join()
        self._renderer.join()
        self._led.join()
        self._sensor.join()
        self._mqtt.stop()
        self._display_hw.set_led(0.0, 0.0, 0.0)
        self._display_hw.set_backlight(0.0)

        # Final save so a clean shutdown always captures the latest state.
        persistence.save(
            self._state_file,
            self._state.get_current_screen(),
            self._state.get_brightness(),
        )
        logger.info("Shutdown complete")

    def _persist_watcher(self) -> None:
        """Daemon thread: saves state whenever screen or brightness changes."""
        last = (self._state.get_current_screen(), self._state.get_brightness())
        while not self._shutdown.is_set():
            self._shutdown.wait(timeout=1.0)
            current = (self._state.get_current_screen(), self._state.get_brightness())
            if current != last:
                persistence.save(self._state_file, current[0], current[1])
                last = current

    def _handle_signal(self, signum: int, frame: object) -> None:
        logger.info("Received signal %d", signum)
        self._shutdown.set()
