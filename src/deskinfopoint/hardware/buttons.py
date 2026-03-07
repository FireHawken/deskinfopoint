from __future__ import annotations

import logging
import threading
import time
from typing import TYPE_CHECKING

from displayhatmini_lite import DisplayHATMini  # type: ignore[import-untyped]

from ..config import ButtonConfig
from ..state import NavMode, SharedState

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
_LOCKOUT = 0.2          # seconds: after any press, ignore all other buttons


class ButtonHandler:
    """Polls button states and dispatches mode-aware actions.

    Button layout (physical):
      A (top-left)     B (bottom-left)
      X (top-right)    Y (bottom-right)

    DATA mode:
      A → enter settings screen
      B → next data screen
      X → configured mqtt_publish (or no-op)
      Y → configured mqtt_publish (or no-op)

    SETTINGS mode (list navigation):
      A → enter edit mode for highlighted setting
      B → exit settings, return to data screens
      X → move cursor up
      Y → move cursor down

    EDIT mode (change a setting value):
      A → confirm and apply
      B → cancel (discard changes)
      X → increase value
      Y → decrease value
    """

    def __init__(
        self,
        display: DisplayHATMini,
        buttons: dict[str, ButtonConfig],
        state: SharedState,
        mqtt: "MQTTClient",
        shutdown: threading.Event,
    ) -> None:
        self._display = display
        self._buttons = buttons
        self._state = state
        self._mqtt = mqtt
        self._shutdown = shutdown
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
        last_press_time: float = 0.0

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
                        now = time.monotonic()
                        if now - last_press_time >= _LOCKOUT:
                            self._on_press(name)
                            last_press_time = now
                            for other in counts:
                                if other != name:
                                    counts[other] = 0
                    stable_state[name] = pressed

            self._shutdown.wait(timeout=_POLL_INTERVAL)

        logger.info("Button polling stopped")

    def _on_press(self, name: str) -> None:
        # Night mode: any press wakes; the press itself is consumed.
        if self._state.is_night_sleeping():
            self._state.night_wake()
            return

        mode = self._state.get_nav_mode()

        if mode == NavMode.DATA:
            if name == "A":
                self._state.enter_settings()
                logger.debug("→ enter settings")
            elif name == "B":
                self._state.next_screen()
                logger.debug("→ next screen (%d)", self._state.get_current_screen())
            elif name in ("X", "Y"):
                cfg = self._buttons.get(name)
                if cfg and cfg.action == "mqtt_publish":
                    self._mqtt.publish(cfg.topic, cfg.payload)
                    logger.debug("Button %s → publish %s = %r", name, cfg.topic, cfg.payload)

        elif mode == NavMode.SETTINGS:
            if name == "A":
                self._state.enter_edit()
                logger.debug("→ enter edit (cursor=%d)", self._state.get_settings_cursor())
            elif name == "B":
                self._state.exit_settings()
                logger.debug("→ exit settings")
            elif name == "X":
                self._state.settings_move(-1)   # cursor up
            elif name == "Y":
                self._state.settings_move(1)    # cursor down

        elif mode == NavMode.EDIT:
            if name == "A":
                self._state.confirm_edit()
                logger.debug("→ confirm edit")
            elif name == "B":
                self._state.cancel_edit()
                logger.debug("→ cancel edit")
            elif name == "X":
                self._state.edit_step(1)    # increase
            elif name == "Y":
                self._state.edit_step(-1)   # decrease
