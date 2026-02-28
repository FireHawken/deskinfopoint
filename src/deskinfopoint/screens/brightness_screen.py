from __future__ import annotations

from PIL import Image, ImageDraw

from ..state import SharedState
from .base import HEIGHT, WIDTH, Screen, load_font

_STEP = 0.1
_BAR_X0 = 20
_BAR_X1 = WIDTH - 20
_BAR_Y0 = 148
_BAR_Y1 = 172
_BAR_W = _BAR_X1 - _BAR_X0


class BrightnessScreen(Screen):
    """Brightness control screen.

    Buttons X and Y adjust backlight brightness in 10% steps.
    These button events are consumed here and do not fall through to the
    global button config.
    """

    def handle_button(self, name: str, state: SharedState, display) -> bool:
        if name == "X":
            new = max(0.05, round(state.get_brightness() - _STEP, 2))
            state.set_brightness(new)
            display.set_backlight(new)
            return True
        if name == "Y":
            new = min(1.0, round(state.get_brightness() + _STEP, 1))
            state.set_brightness(new)
            display.set_backlight(new)
            return True
        return False

    def render(self, state: SharedState) -> Image.Image:
        brightness = state.get_brightness()
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
                radius=6, fill="#f0c040",
            )

        # Tick marks at 10% intervals
        for i in range(1, 10):
            tx = _BAR_X0 + int(_BAR_W * i / 10)
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
