from __future__ import annotations

import logging
import threading

from ..config import SensorConfig
from ..state import SharedState

logger = logging.getLogger(__name__)


class SCD30Sensor:
    """Reads CO2, temperature, and humidity from an Adafruit SCD-30 via I2C.

    Runs in a dedicated daemon thread; polls the sensor at the configured
    measurement_interval and writes readings to SharedState.
    """

    def __init__(
        self,
        config: SensorConfig,
        state: SharedState,
        shutdown: threading.Event,
    ) -> None:
        self._config = config
        self._state = state
        self._shutdown = shutdown
        self._thread = threading.Thread(
            target=self._run, name="scd30", daemon=False
        )

    def start(self) -> None:
        self._thread.start()

    def join(self) -> None:
        self._thread.join()

    def _run(self) -> None:
        try:
            import board  # type: ignore[import-untyped]
            import busio  # type: ignore[import-untyped]
            import adafruit_scd30  # type: ignore[import-untyped]
        except ImportError as e:
            logger.error("SCD-30 dependencies not available: %s. Sensor disabled.", e)
            return

        try:
            i2c = busio.I2C(board.SCL, board.SDA, frequency=50000)
            scd = adafruit_scd30.SCD30(i2c)
            scd.measurement_interval = self._config.measurement_interval
            scd.temperature_offset = self._config.temperature_offset
            if self._config.altitude:
                scd.altitude = self._config.altitude
        except Exception:
            logger.exception("Failed to initialise SCD-30 sensor")
            return

        logger.info(
            "SCD-30 initialised (interval=%ds, offset=%.1f°C, altitude=%dm)",
            self._config.measurement_interval,
            self._config.temperature_offset,
            self._config.altitude,
        )

        poll_interval = max(2, self._config.measurement_interval)
        while not self._shutdown.is_set():
            try:
                if scd.data_available:
                    co2 = scd.CO2
                    temp = scd.temperature
                    rh = scd.relative_humidity
                    self._state.update_sensor(co2=co2, temperature=temp, humidity=rh)
                    logger.debug("SCD-30 read: CO2=%.0f ppm  T=%.1f°C  RH=%.0f%%", co2, temp, rh)
            except Exception:
                logger.exception("SCD-30 read error")

            self._shutdown.wait(timeout=poll_interval)

        logger.info("SCD-30 sensor thread stopped")
