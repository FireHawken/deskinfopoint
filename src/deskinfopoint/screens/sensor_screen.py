from __future__ import annotations

from PIL import Image

from ..config import ScreenConfig, SensorItem
from ..state import SharedState
from .base import (
    ITEMS_Y0, ITEMS_Y1, WIDTH,
    Screen, load_font, value_font_size,
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

        items_h = ITEMS_Y1 - ITEMS_Y0
        row_h = items_h // n
        val_size = value_font_size(row_h)
        val_font = load_font(val_size, bold=True)
        label_font = load_font(13)
        unit_font = load_font(max(13, val_size // 2))

        for i, item in enumerate(self._items):
            y_top = ITEMS_Y0 + i * row_h

            raw = getattr(reading, item.source, None)
            text = self._format_value(raw, item.format)

            # Pick colour: CO2 gets colour-coded, others use white
            if item.source == "co2":
                colour = _co2_colour(raw)
            else:
                colour = "#e8e8e8"

            # Label
            draw.text((10, y_top + 4), item.label, font=label_font, fill="#778899")

            # Value
            draw.text((10, y_top + 20), text, font=val_font, fill=colour)

            # Unit — right of value on the baseline
            if item.unit:
                val_w = int(draw.textlength(text, font=val_font))
                unit_y = y_top + 20 + val_size - int(unit_font.size) - 2
                draw.text((14 + val_w, unit_y), item.unit, font=unit_font, fill="#778899")

            # Row separator (skip after last row)
            if i < n - 1:
                sep_y = y_top + row_h
                draw.line([0, sep_y, WIDTH, sep_y], fill="#1e1e2e", width=1)

        self._draw_screen_dots(draw, state.get_screen_count(), state.get_current_screen())
        return img
