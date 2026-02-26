from __future__ import annotations

from PIL import Image

from ..config import MqttItem, ScreenConfig, SubscriptionConfig
from ..state import SharedState
from .base import (
    ITEMS_Y0, ITEMS_Y1, WIDTH,
    Screen, load_font, value_font_size,
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

        items_h = ITEMS_Y1 - ITEMS_Y0
        row_h = items_h // n
        val_size = value_font_size(row_h)
        val_font = load_font(val_size, bold=True)
        label_font = load_font(13)
        unit_font = load_font(max(13, val_size // 2))

        for i, item in enumerate(self._items):
            y_top = ITEMS_Y0 + i * row_h

            sub = self._subs.get(item.subscription_id)
            if sub is None:
                draw.text((10, y_top + 4), item.subscription_id, font=label_font, fill="#ff4444")
                draw.text((10, y_top + 20), "no subscription", font=val_font, fill="#ff4444")
                continue

            raw = state.get_mqtt(item.subscription_id)
            text = self._format_value(raw, item.format)

            # Label from subscription definition
            draw.text((10, y_top + 4), sub.label, font=label_font, fill="#778899")

            # Value
            draw.text((10, y_top + 20), text, font=val_font, fill="#e8e8e8")

            # Unit
            if sub.unit:
                val_w = int(draw.textlength(text, font=val_font))
                unit_y = y_top + 20 + val_size - int(unit_font.size) - 2
                draw.text((14 + val_w, unit_y), sub.unit, font=unit_font, fill="#778899")

            # Row separator
            if i < n - 1:
                sep_y = y_top + row_h
                draw.line([0, sep_y, WIDTH, sep_y], fill="#1e1e2e", width=1)

        self._draw_screen_dots(draw, state.get_screen_count(), state.get_current_screen())
        return img
