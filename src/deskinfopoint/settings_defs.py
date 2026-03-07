from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .state import SharedState


@dataclass
class SettingDef:
    label: str
    step: float
    min_val: float
    max_val: float
    getter: Callable[["SharedState"], float]


SETTINGS: list[SettingDef] = [
    SettingDef(
        label="Brightness",
        step=0.1,
        min_val=0.05,
        max_val=1.0,
        getter=lambda s: s.get_brightness(),
    ),
    SettingDef(
        label="LED Brightness",
        step=0.1,
        min_val=0.0,
        max_val=1.0,
        getter=lambda s: s.get_led_brightness(),
    ),
]
