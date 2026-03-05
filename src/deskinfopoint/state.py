from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .config import NightModeConfig


@dataclass
class SensorReading:
    co2: float | None = None
    temperature: float | None = None
    humidity: float | None = None
    timestamp: float = 0.0   # time.monotonic() of last successful read


class SharedState:
    """Central thread-safe data bus for all application state."""

    def __init__(
        self,
        screen_count: int,
        initial_brightness: float = 1.0,
        initial_led_brightness: float = 1.0,
        night_mode: "NightModeConfig | None" = None,
    ) -> None:
        self._lock = threading.Lock()
        self._sensor = SensorReading()
        self._mqtt: dict[str, Any] = {}
        self._current_screen = 0
        self._screen_count = screen_count
        self._brightness: float = max(0.05, min(1.0, initial_brightness))
        self._led_brightness: float = max(0.0, min(1.0, initial_led_brightness))
        self._night_mode = night_mode
        self._night_wake_until: float = 0.0   # monotonic; 0 = not woken
        self._version: int = 0  # incremented on every write; readers use this to skip redundant work

    # --- Version (change detection) ---

    def get_version(self) -> int:
        with self._lock:
            return self._version

    # --- Screen navigation ---

    def get_screen_count(self) -> int:
        return self._screen_count  # immutable after construction

    def get_current_screen(self) -> int:
        with self._lock:
            return self._current_screen

    def next_screen(self) -> None:
        with self._lock:
            self._current_screen = (self._current_screen + 1) % self._screen_count
            self._version += 1

    def prev_screen(self) -> None:
        with self._lock:
            self._current_screen = (self._current_screen - 1) % self._screen_count
            self._version += 1

    # --- Sensor data ---

    def update_sensor(self, co2: float, temperature: float, humidity: float) -> None:
        with self._lock:
            self._sensor = SensorReading(
                co2=co2,
                temperature=temperature,
                humidity=humidity,
                timestamp=time.monotonic(),
            )
            self._version += 1

    def get_sensor(self) -> SensorReading:
        with self._lock:
            return self._sensor   # dataclass is replaced atomically on each update

    # --- Backlight brightness ---

    def get_brightness(self) -> float:
        with self._lock:
            return self._brightness

    def set_brightness(self, value: float) -> None:
        with self._lock:
            self._brightness = max(0.05, min(1.0, round(value, 2)))
            self._version += 1

    # --- LED brightness ---

    def get_led_brightness(self) -> float:
        with self._lock:
            return self._led_brightness

    def set_led_brightness(self, value: float) -> None:
        with self._lock:
            self._led_brightness = max(0.0, min(1.0, round(value, 2)))
            self._version += 1

    # --- Night mode ---

    def is_night_sleeping(self) -> bool:
        """Return True if night mode window is active and the wake period has expired."""
        if self._night_mode is None:
            return False
        now = datetime.now().time()
        start, end = self._night_mode.start, self._night_mode.end
        # Overnight span (e.g. 22:00–07:00): active when now >= start OR now < end
        if start > end:
            in_window = now >= start or now < end
        else:
            in_window = start <= now < end
        if not in_window:
            return False
        with self._lock:
            return time.monotonic() >= self._night_wake_until

    def night_wake(self) -> None:
        """Temporarily wake from night mode sleep for the configured duration."""
        if self._night_mode is None:
            return
        with self._lock:
            self._night_wake_until = time.monotonic() + self._night_mode.wake_duration
            self._version += 1

    # --- MQTT values ---

    def update_mqtt(self, sub_id: str, value: Any) -> None:
        with self._lock:
            self._mqtt[sub_id] = value
            self._version += 1

    def get_mqtt(self, sub_id: str) -> Any:
        with self._lock:
            return self._mqtt.get(sub_id)

    def get_all_mqtt(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._mqtt)
