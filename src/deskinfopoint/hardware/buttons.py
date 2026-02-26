from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

from displayhatmini_lite import DisplayHATMini  # type: ignore[import-untyped]

from ..config import ButtonConfig
from ..screens.base import Screen
from ..state import SharedState

if TYPE_CHECKING:
    from ..mqtt_client import MQTTClient

logger = logging.getLogger(__name__)

_BUTTON_PINS: dict[str, int] = {
    "A": DisplayHATMini.BUTTON_A,
    "B": DisplayHATMini.BUTTON_B,
    "X": DisplayHATMini.BUTTON_X,
    "Y": DisplayHATMini.BUTTON_Y,
}

_POLL_INTERVAL = 0.05   # 50 ms — responsive enough, low CPU overhead
_DEBOUNCE_COUNT = 2     # require N consecutive identical reads before acting


class ButtonHandler:
    """Polls button states in a thread and dispatches configured actions on press.

    Before falling through to the global button config, the current screen's
    handle_button() is called.  This lets screens like BrightnessScreen intercept
    X/Y for local actions without changing the global config.

    GPIO.add_event_detect is broken on Linux 6.x with RPi.GPIO 0.7.x due to the
    sysfs GPIO base offset change (gpiochip512).  Polling via GPIO.input() works
    correctly and is the safe cross-kernel approach.
    """

    def __init__(
        self,
        display: DisplayHATMini,
        buttons: dict[str, ButtonConfig],
        state: SharedState,
        mqtt: "MQTTClient",
        shutdown: threading.Event,
        screens: list[Screen],
    ) -> None:
        self._display = display
        self._buttons = buttons
        self._state = state
        self._mqtt = mqtt
        self._shutdown = shutdown
        self._screens = screens
        self._thread = threading.Thread(
            target=self._run, name="buttons", daemon=False
        )

    def start(self) -> None:
        self._thread.start()
        logger.info("Button polling started")

    def join(self) -> None:
        self._thread.join()

    def _run(self) -> None:
        prev_state: dict[str, bool] = {name: False for name in _BUTTON_PINS}
        stable_state: dict[str, bool] = {name: False for name in _BUTTON_PINS}
        counts: dict[str, int] = {name: 0 for name in _BUTTON_PINS}

        while not self._shutdown.is_set():
            for name, pin in _BUTTON_PINS.items():
                pressed = self._display.read_button(pin)
                if pressed == prev_state[name]:
                    counts[name] += 1
                else:
                    counts[name] = 1
                    prev_state[name] = pressed

                if counts[name] == _DEBOUNCE_COUNT:
                    if pressed and not stable_state[name]:
                        self._on_press(name)
                    stable_state[name] = pressed

            self._shutdown.wait(timeout=_POLL_INTERVAL)

        logger.info("Button polling stopped")

    def _on_press(self, name: str) -> None:
        # Give the current screen first chance to handle the button.
        screen = self._screens[self._state.get_current_screen()]
        if screen.handle_button(name, self._state, self._display):
            return

        # Fall through to global config.
        cfg = self._buttons.get(name)
        if cfg is None:
            logger.debug("Button %s pressed but not configured", name)
            return
        self._dispatch(name, cfg)

    def _dispatch(self, name: str, cfg: ButtonConfig) -> None:
        if cfg.action == "next_screen":
            self._state.next_screen()
            logger.debug("Button %s → next screen (%d)", name, self._state.get_current_screen())
        elif cfg.action == "prev_screen":
            self._state.prev_screen()
            logger.debug("Button %s → prev screen (%d)", name, self._state.get_current_screen())
        elif cfg.action == "mqtt_publish":
            self._mqtt.publish(cfg.topic, cfg.payload)
            logger.debug("Button %s → publish %s = %r", name, cfg.topic, cfg.payload)
        else:
            logger.warning("Button %s: unknown action %r", name, cfg.action)
