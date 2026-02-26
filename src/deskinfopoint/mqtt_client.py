from __future__ import annotations

import json
import logging
import queue
from typing import Any

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from .config import MqttConfig, SubscriptionConfig
from .state import SharedState

logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(
        self,
        config: MqttConfig,
        subscriptions: list[SubscriptionConfig],
        state: SharedState,
    ) -> None:
        self._config = config
        self._subs_by_topic: dict[str, SubscriptionConfig] = {
            s.topic: s for s in subscriptions
        }
        self._state = state
        self._publish_queue: queue.Queue[tuple[str, str]] = queue.Queue()

        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=config.client_id,
            reconnect_on_failure=True,
        )
        if config.username:
            self._client.username_pw_set(config.username, config.password)

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._client.on_disconnect = self._on_disconnect

    def start(self) -> None:
        self._client.connect_async(
            self._config.broker, self._config.port, self._config.keepalive, clean_start=True
        )
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def publish(self, topic: str, payload: str) -> None:
        """Thread-safe: enqueue a publish for the paho network thread."""
        self._publish_queue.put((topic, payload))

    # --- paho callbacks (run in paho's network thread) ---

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            logger.error("MQTT connect failed: %s", reason_code)
            return
        logger.info("MQTT connected to %s:%d", self._config.broker, self._config.port)
        for topic in self._subs_by_topic:
            client.subscribe(topic, qos=1)
            logger.debug("Subscribed to %s", topic)
        # Drain any queued publishes that arrived before connection was up
        self._drain_publish_queue(client)

    def _on_message(self, client, userdata, message) -> None:
        sub = self._subs_by_topic.get(message.topic)
        if sub is None:
            return
        try:
            raw = message.payload.decode("utf-8", errors="replace")
            value = self._extract_value(raw, sub.value_path)
            self._state.update_mqtt(sub.id, value)
            logger.debug("MQTT %s → %s = %r", message.topic, sub.id, value)
        except Exception:
            logger.exception("Error processing MQTT message on %s", message.topic)
        # Drain any pending publishes each time a message arrives
        self._drain_publish_queue(client)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            logger.warning("MQTT disconnected unexpectedly (%s); will reconnect", reason_code)

    def _drain_publish_queue(self, client) -> None:
        while not self._publish_queue.empty():
            try:
                topic, payload = self._publish_queue.get_nowait()
                client.publish(topic, payload, qos=1)
                logger.info("Published %s → %r", topic, payload)
            except queue.Empty:
                break

    def _extract_value(self, raw: str, value_path: str) -> Any:
        """Return a float if possible, else str.  Traverses dot-notation JSON path."""
        if not value_path:
            raw = raw.strip()
            try:
                return float(raw)
            except ValueError:
                return raw

        data = json.loads(raw)
        for key in value_path.split("."):
            if isinstance(data, list):
                data = data[int(key)]
            else:
                data = data[key]
        try:
            return float(data)
        except (ValueError, TypeError):
            return str(data)
