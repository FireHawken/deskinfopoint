from __future__ import annotations

from PIL import Image, ImageDraw

from ..state import SharedState
from .base import HEIGHT, WIDTH, Screen, load_font

_LEVELS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
_BAR_X0 = 20
_BAR_X1 = WIDTH - 20
_BAR_Y0 = 148
_BAR_Y1 = 172
_BAR_W = _BAR_X1 - _BAR_X0


def _nearest_level(value: float) -> int:
    """Return the index in _LEVELS closest to value."""
    return min(range(len(_LEVELS)), key=lambda i: abs(_LEVELS[i] - value))


class LedBrightnessScreen(Screen):
    """LED brightness control screen.

    Buttons X and Y step through _LEVELS (0%, 2%, 5%, 10%, 20% … 100%).
    These button events are consumed here and do not fall through to the
    global button config.
    """

    def handle_button(self, name: str, state: SharedState, display) -> bool:
        if name == "X":
            current = state.get_led_brightness()
            idx = _nearest_level(current)
            if idx > 0:
                state.set_led_brightness(_LEVELS[idx - 1])
            return True
        if name == "Y":
            current = state.get_led_brightness()
            idx = _nearest_level(current)
            if idx < len(_LEVELS) - 1:
                state.set_led_brightness(_LEVELS[idx + 1])
            return True
        return False

    def render(self, state: SharedState) -> Image.Image:
        brightness = state.get_led_brightness()
        pct = int(round(brightness * 100))

        img, draw = self._new_image()
        self._draw_header(draw)

        # Large percentage value
        val_font = load_font(80, bold=True)
        label_font = load_font(14)
        hint_font = load_font(15, bold=True)

        val_text = f"{pct}%"
        val_w = int(draw.textlength(val_text, font=val_font))
        draw.text(((WIDTH - val_w) // 2, 38), val_text, font=val_font, fill="#f0f0f0")

        # Progress bar background
        draw.rounded_rectangle(
            [_BAR_X0, _BAR_Y0, _BAR_X1, _BAR_Y1],
            radius=6, fill="#2a2a2a",
        )
        # Progress bar fill
        fill_w = int(_BAR_W * brightness)
        if fill_w > 0:
            draw.rounded_rectangle(
                [_BAR_X0, _BAR_Y0, _BAR_X0 + fill_w, _BAR_Y1],
                radius=6, fill="#60b0ff",
            )

        # Tick marks at each level
        for lvl in _LEVELS[1:-1]:
            tx = _BAR_X0 + int(_BAR_W * lvl)
            draw.line([tx, _BAR_Y0 + 2, tx, _BAR_Y1 - 2], fill="#0a0a0a", width=1)

        # Button hints
        draw.text((10, 192), "X", font=hint_font, fill="#888888")
        draw.text((30, 193), "dim", font=label_font, fill="#555555")

        plus_label = "brighten"
        plus_w = int(draw.textlength(plus_label, font=label_font))
        hint_w = int(draw.textlength("Y", font=hint_font))
        draw.text((WIDTH - 10 - plus_w - 6 - hint_w, 193), plus_label, font=label_font, fill="#555555")
        draw.text((WIDTH - 10 - hint_w, 192), "Y", font=hint_font, fill="#888888")

        self._draw_screen_dots(draw, state.get_screen_count(), state.get_current_screen())
        return img
