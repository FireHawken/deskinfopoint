from __future__ import annotations

from PIL import Image

from ..config import MqttItem, ScreenConfig, SubscriptionConfig
from ..state import SharedState
from .base import (
    ITEMS_Y0, ITEMS_Y1, WIDTH,
    Screen, cell_layout, load_font,
)


class MQTTScreen(Screen):
    """Displays values received from configured MQTT subscriptions.

    Labels and units are taken from the subscription definition in config.yaml.
    """

    def __init__(
        self,
        config: ScreenConfig,
        subscriptions: dict[str, SubscriptionConfig],
    ) -> None:
        super().__init__(config.name)
        self._items: list[MqttItem] = config.items  # type: ignore[assignment]
        self._subs = subscriptions

    def render(self, state: SharedState) -> Image.Image:
        img, draw = self._new_image()
        self._draw_header(draw)

        n = len(self._items)
        if n == 0:
            return img

        cells = cell_layout(n, ITEMS_Y0, ITEMS_Y1, WIDTH)

        for item, (x0, y0, x1, y1, featured) in zip(self._items, cells):
            sub = self._subs.get(item.subscription_id)
            if sub is None:
                ef = load_font(13)
                draw.text((x0 + 10, y0 + 4), item.subscription_id, font=ef, fill="#ff4444")
                draw.text((x0 + 10, y0 + 20), "no subscription", font=ef, fill="#ff4444")
                continue

            raw = state.get_mqtt(item.subscription_id)
            if raw is not None and sub.value_map:
                raw = sub.value_map.get(str(raw), str(raw))
            text = self._format_value(raw, item.format)
            self._draw_item_cell(draw, x0, y0, x1, y1, featured, sub.label, text, sub.unit, "#e8e8e8")

        self._draw_cell_separators(draw, cells)
        self._draw_screen_dots(draw, state.get_screen_count(), state.get_current_screen())
        return img
