from __future__ import annotations

import logging
import threading
import time

from ..screens.base import Screen
from ..state import NavMode, SharedState

logger = logging.getLogger(__name__)


class DisplayController:
    """Render loop: picks the active screen, renders it, pushes to display.

    In DATA mode the current data screen is rendered.
    In SETTINGS or EDIT mode the settings screen is rendered instead.

    Runs in its own thread.  Frame timing uses shutdown_event.wait() so it
    responds to the shutdown signal immediately rather than after a full frame.
    """

    def __init__(
        self,
        display,  # DisplayHATMini
        screens: list[Screen],
        state: SharedState,
        fps: int,
        shutdown: threading.Event,
        settings_screen: Screen,
    ) -> None:
        self._display = display
        self._screens = screens
        self._state = state
        self._frame_time = 1.0 / max(1, fps)
        self._shutdown = shutdown
        self._settings_screen = settings_screen
        self._thread = threading.Thread(
            target=self._run, name="render", daemon=False
        )

    def start(self) -> None:
        self._thread.start()

    def join(self) -> None:
        self._thread.join()

    def _run(self) -> None:
        logger.info("Display render loop started (%.0f FPS)", 1.0 / self._frame_time)
        last_version = -1
        last_minute = -1
        last_brightness: float = self._state.get_brightness()
        was_sleeping = False

        while not self._shutdown.is_set():
            sleeping = self._state.is_night_sleeping()

            if sleeping != was_sleeping:
                was_sleeping = sleeping
                if sleeping:
                    self._display.set_backlight(0.0)
                    logger.info("Night mode: display off")
                else:
                    self._display.set_backlight(self._state.get_brightness())
                    last_version = -1
                    logger.info("Night mode: display on")

            if sleeping:
                self._shutdown.wait(timeout=1.0)
                continue

            # Apply brightness changes immediately (e.g. confirmed from settings).
            brightness = self._state.get_brightness()
            if brightness != last_brightness:
                self._display.set_backlight(brightness)
                last_brightness = brightness

            # Force re-render when the minute changes so the clock stays current.
            current_minute = time.localtime().tm_min
            if current_minute != last_minute:
                last_minute = current_minute
                last_version = -1

            version = self._state.get_version()
            if version != last_version:
                t0 = time.monotonic()
                nav_mode = self._state.get_nav_mode()
                if nav_mode != NavMode.DATA:
                    screen = self._settings_screen
                else:
                    idx = self._state.get_current_screen()
                    screen = self._screens[idx]
                try:
                    image = screen.render(self._state)
                    self._display.display(image)
                    last_version = version
                except Exception:
                    logger.exception("Render error on screen %s", screen.name)
                elapsed = time.monotonic() - t0
                sleep_time = max(0.0, self._frame_time - elapsed)
            else:
                sleep_time = self._frame_time
            self._shutdown.wait(timeout=sleep_time)

        logger.info("Display render loop stopped")
