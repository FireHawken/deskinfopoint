from __future__ import annotations

import json
import logging
import threading
from typing import TYPE_CHECKING

from ..config import SensorConfig
from ..state import SharedState

if TYPE_CHECKING:
    from ..mqtt_client import MQTTClient

logger = logging.getLogger(__name__)


class SCD30Sensor:
    """Reads CO2, temperature, and humidity from an Adafruit SCD-30 via I2C.

    Runs in a dedicated daemon thread; polls the sensor at the configured
    measurement_interval and writes readings to SharedState.  If
    config.publish_topic is set, each reading is also published as JSON
    to that MQTT topic.
    """

    def __init__(
        self,
        config: SensorConfig,
        state: SharedState,
        shutdown: threading.Event,
        mqtt: MQTTClient | None = None,
    ) -> None:
        self._config = config
        self._state = state
        self._shutdown = shutdown
        self._mqtt = mqtt
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

        scd = None
        for attempt in range(1, 13):   # up to 12 attempts (~60 s)
            try:
                i2c = busio.I2C(board.SCL, board.SDA, frequency=50000)
                scd = adafruit_scd30.SCD30(i2c)
                scd.measurement_interval = self._config.measurement_interval
                scd.temperature_offset = self._config.temperature_offset
                if self._config.altitude:
                    scd.altitude = self._config.altitude
                break
            except Exception as e:
                logger.warning(
                    "SCD-30 init attempt %d/12 failed: %s — retrying in 5 s", attempt, e
                )
                if self._shutdown.wait(timeout=5):
                    return   # shutdown requested while waiting

        if scd is None:
            logger.error("SCD-30 failed to initialise after 12 attempts; sensor disabled")
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
                    if self._mqtt and self._config.publish_topic:
                        payload = json.dumps({
                            "co2": round(co2),
                            "temperature": round(temp, 1),
                            "humidity": round(rh, 1),
                        })
                        self._mqtt.publish(self._config.publish_topic, payload)
            except Exception:
                logger.exception("SCD-30 read error")

            self._shutdown.wait(timeout=poll_interval)

        logger.info("SCD-30 sensor thread stopped")
