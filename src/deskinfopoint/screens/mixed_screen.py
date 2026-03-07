from __future__ import annotations

from PIL import Image

from ..config import MixedItem, ScreenConfig, SubscriptionConfig
from ..state import SharedState
from .base import ITEMS_Y0, ITEMS_Y1, WIDTH, Screen, cell_layout

# CO2 colour thresholds (shared logic with sensor_screen)
_CO2_COLOURS = [
    (1500, "#f44336"),
    (1000, "#ff9800"),
    (800,  "#ffee58"),
    (0,    "#00e676"),
]


def _co2_colour(co2: float | None) -> str:
    if co2 is None:
        return "#888888"
    for threshold, colour in _CO2_COLOURS:
        if co2 >= threshold:
            return colour
    return "#00e676"


class MixedScreen(Screen):
    """Screen that can display both SCD-30 sensor readings and MQTT values."""

    def __init__(
        self,
        config: ScreenConfig,
        subscriptions: dict[str, SubscriptionConfig],
    ) -> None:
        super().__init__(config.name)
        self._items: list[MixedItem] = config.items  # type: ignore[assignment]
        self._subs = subscriptions

    def render(self, state: SharedState) -> Image.Image:
        img, draw = self._new_image()
        self._draw_header(draw)

        n = len(self._items)
        if n == 0:
            return img

        cells = cell_layout(n, ITEMS_Y0, ITEMS_Y1, WIDTH)

        reading = state.get_sensor()

        for item, (x0, y0, x1, y1, featured) in zip(self._items, cells):
            if item.source:
                # --- sensor item ---
                raw = getattr(reading, item.source, None)
                text = self._format_value(raw, item.format)
                colour = _co2_colour(raw) if item.source == "co2" else "#e8e8e8"
                label = item.label or item.source
                unit = item.unit
            else:
                # --- MQTT item ---
                sub = self._subs.get(item.subscription_id)
                if sub is None:
                    from .base import load_font
                    ef = load_font(13)
                    draw.text((x0 + 10, y0 + 4), item.subscription_id, font=ef, fill="#ff4444")
                    draw.text((x0 + 10, y0 + 20), "no subscription", font=ef, fill="#ff4444")
                    continue
                raw = state.get_mqtt(item.subscription_id)
                if raw is not None and sub.value_map:
                    raw = sub.value_map.get(str(raw), str(raw))
                text = self._format_value(raw, item.format)
                colour = "#e8e8e8"
                label = item.label or sub.label
                unit = item.unit or sub.unit

            self._draw_item_cell(draw, x0, y0, x1, y1, featured, label, text, unit, colour)

        self._draw_cell_separators(draw, cells)
        self._draw_screen_dots(draw, state.get_screen_count(), state.get_current_screen())
        return img
