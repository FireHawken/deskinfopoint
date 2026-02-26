from __future__ import annotations

import operator as op_module

from .config import AlertConfig
from .state import SharedState, SensorReading

_OPS: dict[str, Any] = {
    ">=": op_module.ge,
    "<=": op_module.le,
    "!=": op_module.ne,
    ">":  op_module.gt,
    "<":  op_module.lt,
    "==": op_module.eq,
}

# Satisfy the type checker; op_module returns bool
from typing import Any


class AlertEvaluator:
    """Evaluates alert conditions against current state.

    Alerts are sorted by priority (descending) at construction time.
    The first matching alert is returned — highest priority wins.
    """

    def __init__(self, alerts: list[AlertConfig], state: SharedState) -> None:
        self._alerts = sorted(alerts, key=lambda a: a.priority, reverse=True)
        self._state = state

    def active_alert(self) -> AlertConfig | None:
        sensor = self._state.get_sensor()
        mqtt_vals = self._state.get_all_mqtt()
        for alert in self._alerts:
            value = self._resolve(alert.source, sensor, mqtt_vals)
            if value is not None and self._eval(value, alert.op, alert.threshold):
                return alert
        return None

    def _resolve(
        self,
        source: str,
        sensor: SensorReading,
        mqtt_vals: dict[str, Any],
    ) -> Any:
        ns, _, field = source.partition(".")
        if ns == "sensor":
            return getattr(sensor, field, None)
        if ns == "mqtt":
            return mqtt_vals.get(field)
        return None

    def _eval(self, value: Any, op_str: str, threshold: Any) -> bool:
        fn = _OPS.get(op_str)
        if fn is None:
            return False
        try:
            return bool(fn(value, threshold))
        except TypeError:
            return False
