from __future__ import annotations

import logging
import math
import threading

from ..alerts import AlertEvaluator
from ..config import LedIdleConfig

logger = logging.getLogger(__name__)

_TICK = 0.05        # 20 Hz — smooth enough for pulse/blink animation
_TICK_SOLID = 0.5   # 2 Hz — sufficient to detect alert transitions when LED is steady


class LEDController:
    """Drives the Display HAT Mini's RGB LED based on alert conditions.

    Runs in its own thread so animation doesn't block the render loop.
    Evaluates alerts at each tick; the highest-priority active alert wins.
    """

    def __init__(
        self,
        display,  # DisplayHATMini instance
        evaluator: AlertEvaluator,
        idle: LedIdleConfig,
        shutdown: threading.Event,
    ) -> None:
        self._display = display
        self._evaluator = evaluator
        self._idle = idle
        self._shutdown = shutdown
        self._thread = threading.Thread(
            target=self._run, name="led", daemon=False
        )

    def start(self) -> None:
        self._thread.start()

    def join(self) -> None:
        self._thread.join()

    def _run(self) -> None:
        t = 0.0
        _last_solid_rgb: tuple[float, float, float] | None = None
        while not self._shutdown.is_set():
            alert = self._evaluator.active_alert()
            cfg = alert if alert is not None else self._idle
            r, g, b = cfg.color
            mode = cfg.mode

            if mode == "blink":
                _last_solid_rgb = None
                hz = getattr(cfg, "blink_hz", 2.0)
                on = (t * hz) % 1.0 < 0.5
                self._display.set_led(r * on, g * on, b * on)
                self._shutdown.wait(timeout=_TICK)
                t += _TICK
            elif mode == "pulse":
                _last_solid_rgb = None
                hz = getattr(cfg, "pulse_hz", 1.0)
                brightness = (math.sin(2 * math.pi * hz * t) + 1.0) / 2.0
                self._display.set_led(r * brightness, g * brightness, b * brightness)
                self._shutdown.wait(timeout=_TICK)
                t += _TICK
            else:  # solid — set once on change, then sleep longer
                rgb = (r, g, b)
                if rgb != _last_solid_rgb:
                    self._display.set_led(r, g, b)
                    _last_solid_rgb = rgb
                self._shutdown.wait(timeout=_TICK_SOLID)
                t += _TICK_SOLID

        self._display.set_led(0.0, 0.0, 0.0)
        logger.info("LED controller stopped")
