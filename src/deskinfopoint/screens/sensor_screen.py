from __future__ import annotations

from PIL import Image

from ..config import ScreenConfig, SensorItem
from ..state import SharedState
from .base import (
    ITEMS_Y0, ITEMS_Y1, WIDTH,
    Screen, cell_layout,
)

# CO2-specific colour thresholds (ppm)
_CO2_COLOURS = [
    (1500, "#f44336"),  # red    — danger
    (1000, "#ff9800"),  # orange — poor
    (800,  "#ffee58"),  # yellow — moderate
    (0,    "#00e676"),  # green  — good
]


def _co2_colour(co2: float | None) -> str:
    if co2 is None:
        return "#888888"
    for threshold, colour in _CO2_COLOURS:
        if co2 >= threshold:
            return colour
    return "#00e676"


class SensorScreen(Screen):
    """Displays SCD-30 sensor readings (CO2, temperature, humidity).

    Items are configured in config.yaml; up to 3 items render well at 320×240.
    """

    def __init__(self, config: ScreenConfig) -> None:
        super().__init__(config.name)
        self._items: list[SensorItem] = config.items  # type: ignore[assignment]

    def render(self, state: SharedState) -> Image.Image:
        reading = state.get_sensor()
        img, draw = self._new_image()
        self._draw_header(draw)

        n = len(self._items)
        if n == 0:
            return img

        cells = cell_layout(n, ITEMS_Y0, ITEMS_Y1, WIDTH)

        for item, (x0, y0, x1, y1, featured) in zip(self._items, cells):
            raw = getattr(reading, item.source, None)
            text = self._format_value(raw, item.format)
            colour = _co2_colour(raw) if item.source == "co2" else "#e8e8e8"
            self._draw_item_cell(draw, x0, y0, x1, y1, featured, item.label, text, item.unit, colour)

        self._draw_cell_separators(draw, cells)
        self._draw_screen_dots(draw, state.get_screen_count(), state.get_current_screen())
        return img
