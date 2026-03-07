from __future__ import annotations

from PIL import Image

from ..settings_defs import SETTINGS
from ..state import NavMode, SharedState
from .base import HEIGHT, ITEMS_Y0, ITEMS_Y1, WIDTH, Screen, load_font


class SettingsScreen(Screen):
    """Unified settings screen: list of settings with cursor, edit mode.

    Navigation (managed by ButtonHandler, not this screen):
      SETTINGS mode  — X: cursor up, Y: cursor down, A: enter edit, B: exit
      EDIT mode      — X: increase, Y: decrease, A: confirm, B: cancel
    """

    def __init__(self) -> None:
        super().__init__("Settings")

    def render(self, state: SharedState) -> Image.Image:
        img, draw = self._new_image()
        self._draw_header(draw)

        nav_mode = state.get_nav_mode()
        cursor = state.get_settings_cursor()
        n = len(SETTINGS)
        row_h = (ITEMS_Y1 - ITEMS_Y0) // n

        label_font = load_font(13)
        val_font = load_font(40, bold=True)

        for i, defn in enumerate(SETTINGS):
            y0 = ITEMS_Y0 + i * row_h
            y1 = y0 + row_h
            is_sel = (i == cursor)
            is_edit = is_sel and (nav_mode == NavMode.EDIT)

            # Row background
            if is_edit:
                draw.rectangle([0, y0, WIDTH - 1, y1 - 1], fill="#182048")
            elif is_sel:
                draw.rectangle([0, y0, WIDTH - 1, y1 - 1], fill="#0e1535")

            # Current value to display
            val = state.get_edit_value() if is_edit else defn.getter(state)
            val_text = f"{int(round(val * 100))}%"

            # Label
            draw.text((16, y0 + 10), defn.label, font=label_font, fill="#a0b4c8")

            # Value (right-aligned, yellow when editing)
            val_color = "#ffd700" if is_edit else "#e8e8e8"
            val_w = int(draw.textlength(val_text, font=val_font))
            draw.text((WIDTH - 16 - val_w, y0 + 25), val_text, font=val_font, fill=val_color)

            # Progress bar
            bar_x0, bar_x1 = 16, WIDTH - 16
            bar_y = y0 + 72
            bar_h = 6
            span = defn.max_val - defn.min_val
            fill_frac = max(0.0, min(1.0, (val - defn.min_val) / span if span else val))
            draw.rectangle([bar_x0, bar_y, bar_x1, bar_y + bar_h], fill="#1a2040")
            fill_px = int((bar_x1 - bar_x0) * fill_frac)
            if fill_px > 0:
                bar_color = "#60a0ff" if is_edit else ("#4472c4" if is_sel else "#2a3a6a")
                draw.rectangle([bar_x0, bar_y, bar_x0 + fill_px, bar_y + bar_h], fill=bar_color)

            # Row separator
            if i < n - 1:
                draw.line([0, y1, WIDTH - 1, y1], fill="#1e1e2e", width=1)

        # Hint line in the footer area
        hint_font = load_font(11)
        if nav_mode == NavMode.EDIT:
            hint = "X▲  Y▼       A:confirm  B:cancel"
        else:
            hint = "X▲  Y▼  A:edit       B:exit"
        hint_w = int(draw.textlength(hint, font=hint_font))
        draw.text(((WIDTH - hint_w) // 2, HEIGHT - 12), hint, font=hint_font, fill="#405060")

        return img
