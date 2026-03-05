from __future__ import annotations

import logging
import threading
import time

from ..screens.base import Screen
from ..state import SharedState

logger = logging.getLogger(__name__)


class DisplayController:
    """Render loop: picks the current screen, renders it, pushes to display.

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
    ) -> None:
        self._display = display
        self._screens = screens
        self._state = state
        self._frame_time = 1.0 / max(1, fps)
        self._shutdown = shutdown
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
                    last_version = -1   # force re-render immediately on wake
                    logger.info("Night mode: display on")

            if sleeping:
                self._shutdown.wait(timeout=1.0)
                continue

            version = self._state.get_version()
            if version != last_version:
                t0 = time.monotonic()
                idx = self._state.get_current_screen()
                screen = self._screens[idx]
                try:
                    image = screen.render(self._state)
                    self._display.display(image)
                    last_version = version
                except Exception:
                    logger.exception("Render error on screen %d (%s)", idx, screen.name)
                elapsed = time.monotonic() - t0
                sleep_time = max(0.0, self._frame_time - elapsed)
            else:
                sleep_time = self._frame_time
            self._shutdown.wait(timeout=sleep_time)

        logger.info("Display render loop stopped")
