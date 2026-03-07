from __future__ import annotations

import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont  # type: ignore[import-untyped]

from ..state import SharedState

WIDTH = 320
HEIGHT = 240
HEADER_H = 30
DOTS_H = 14
ITEMS_Y0 = HEADER_H + 2
ITEMS_Y1 = HEIGHT - DOTS_H - 2

_FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu/",
    "/usr/share/fonts/truetype/ttf-dejavu/",
    "/usr/share/fonts/dejavu/",
]


@lru_cache(maxsize=32)
def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in _FONT_DIRS:
        path = os.path.join(d, name)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def value_font_size(row_height: int) -> int:
    """Pick a value font size that comfortably fills the available row height."""
    if row_height >= 150:
        return 80
    if row_height >= 105:
        return 64
    if row_height >= 70:
        return 40
    if row_height >= 55:
        return 32
    return 26


def cell_layout(
    n: int, items_y0: int, items_y1: int, width: int
) -> list[tuple[int, int, int, int, bool]]:
    """Compute (x0, y0, x1, y1, featured) for each of n items.

    Layout rules:
      n=1          → single featured cell, full width
      even n       → 2-col grid, n//2 rows
      odd n >= 3   → 1 featured row (full width) + 2-col grid for remaining n-1
    """
    content_h = items_y1 - items_y0

    if n == 1:
        return [(0, items_y0, width, items_y1, True)]

    if n % 2 == 0:
        rows = n // 2
        row_h = content_h // rows
        half_w = width // 2
        return [
            (
                (i % 2) * half_w,
                items_y0 + (i // 2) * row_h,
                (i % 2 + 1) * half_w,
                items_y0 + (i // 2 + 1) * row_h,
                False,
            )
            for i in range(n)
        ]

    # odd n >= 3: featured first row + 2-col grid
    rest = n - 1
    grid_rows = rest // 2
    # Grid rows have a fixed max height; featured gets the rest
    grid_row_h = min(80, (content_h - 30) // grid_rows)
    featured_h = content_h - grid_row_h * grid_rows
    half_w = width // 2

    cells: list[tuple[int, int, int, int, bool]] = [
        (0, items_y0, width, items_y0 + featured_h, True)
    ]
    grid_y0 = items_y0 + featured_h
    for i in range(rest):
        col = i % 2
        row = i // 2
        cells.append((
            col * half_w,
            grid_y0 + row * grid_row_h,
            (col + 1) * half_w,
            grid_y0 + (row + 1) * grid_row_h,
            False,
        ))
    return cells


# ---------------------------------------------------------------------------
# Status-bar helpers
# ---------------------------------------------------------------------------

_wifi_cache: tuple[float, bool] = (0.0, False)
_WIFI_TTL = 5.0   # re-check every 5 s


def _wifi_connected() -> bool:
    global _wifi_cache
    now = time.monotonic()
    if now - _wifi_cache[0] < _WIFI_TTL:
        return _wifi_cache[1]
    connected = False
    try:
        for iface in os.listdir("/sys/class/net"):
            if iface.startswith("wlan"):
                with open(f"/sys/class/net/{iface}/operstate") as f:
                    if f.read().strip() == "up":
                        connected = True
                        break
    except OSError:
        pass
    _wifi_cache = (now, connected)
    return connected


def _draw_wifi_icon(
    draw: ImageDraw.ImageDraw, cx: int, by: int, connected: bool
) -> None:
    """Minimal wifi icon.  cx = centre x, by = bottom y of icon area."""
    color = "#50a8e0" if connected else "#363636"
    # dot
    draw.ellipse([cx - 1, by - 2, cx + 1, by], fill=color)
    # inner arc
    draw.arc([cx - 4, by - 8, cx + 4, by], 220, 320, fill=color, width=2)
    # outer arc
    draw.arc([cx - 8, by - 16, cx + 8, by], 220, 320, fill=color, width=2)


class Screen(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def render(self, state: SharedState) -> Image.Image:
        """Return a 320×240 RGB PIL Image."""
        ...

    def handle_button(self, name: str, state: SharedState, display) -> bool:
        """Handle a button press before the global config is consulted.

        Return True to consume the event (prevents global dispatch).
        The default implementation does nothing and returns False.
        """
        return False

    # --- Shared drawing helpers ---

    def _new_image(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        img = Image.new("RGB", (WIDTH, HEIGHT), "#0a0a0a")
        draw = ImageDraw.Draw(img)
        return img, draw

    def _draw_header(self, draw: ImageDraw.ImageDraw) -> None:
        draw.rectangle([0, 0, WIDTH - 1, HEADER_H - 1], fill="#141428")
        # Screen name (left)
        draw.text((10, 8), self.name, font=load_font(14, bold=True), fill="#dde6f0")
        # Clock (right)
        clock_text = datetime.now().strftime("%H:%M")
        clock_font = load_font(13)
        clock_w = int(draw.textlength(clock_text, font=clock_font))
        clock_x = WIDTH - 8 - clock_w
        draw.text((clock_x, 9), clock_text, font=clock_font, fill="#7888a0")
        # Wi-Fi icon (left of clock)
        icon_cx = clock_x - 8 - 8   # 8 px gap + half of 16 px icon
        _draw_wifi_icon(draw, icon_cx, HEADER_H - 3, _wifi_connected())

    def _draw_screen_dots(
        self, draw: ImageDraw.ImageDraw, total: int, current: int
    ) -> None:
        if total <= 1:
            return
        dot_r = 3
        spacing = 14
        total_w = (total - 1) * spacing
        x0 = (WIDTH - total_w) // 2
        y = HEIGHT - dot_r - 4
        for i in range(total):
            x = x0 + i * spacing
            color = "#ffffff" if i == current else "#3a3a3a"
            draw.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r], fill=color)

    def _draw_item_cell(
        self,
        draw: ImageDraw.ImageDraw,
        x0: int, y0: int, x1: int, y1: int,
        featured: bool,
        label: str,
        text: str,
        unit: str,
        value_color: str,
    ) -> None:
        """Draw a single item into its cell rect.

        Featured cells: label + value centered, large font.
        Grid cells: label + value left-aligned, capped font size.
        """
        cell_h = y1 - y0
        label_font = load_font(13)

        if featured:
            cx = (x0 + x1) // 2
            val_size = value_font_size(cell_h)
            val_font = load_font(val_size, bold=True)
            unit_font = load_font(max(13, val_size // 2))
            # Center label + value as a tight block vertically in the cell
            lbl_gap = 4  # px between label bottom and value top
            block_h = 13 + lbl_gap + val_size
            block_y = y0 + (cell_h - block_h) // 2
            lbl_w = int(draw.textlength(label, font=label_font))
            draw.text((cx - lbl_w // 2, block_y), label, font=label_font, fill="#a0b4c8")
            # Value + unit block centered horizontally
            val_w = int(draw.textlength(text, font=val_font))
            unit_w = int(draw.textlength(unit, font=unit_font)) if unit else 0
            gap = 4 if unit else 0
            block_w = val_w + gap + unit_w
            val_x = cx - block_w // 2
            val_y = block_y + 13 + lbl_gap
            draw.text((val_x, val_y), text, font=val_font, fill=value_color)
            if unit:
                unit_y = val_y + val_size - int(unit_font.size) - 2
                draw.text((val_x + val_w + gap, unit_y), unit, font=unit_font, fill="#a0b4c8")
        else:
            # Grid cell: centered, auto-shrink value to fit half-width column
            cx = (x0 + x1) // 2
            max_text_w = (x1 - x0) - 20  # 10px padding each side
            val_size = min(value_font_size(cell_h), 36)
            val_font = load_font(val_size, bold=True)
            unit_font = load_font(max(13, val_size // 2))
            val_w = int(draw.textlength(text, font=val_font))
            unit_w = int(draw.textlength(unit, font=unit_font)) if unit else 0
            block_w = val_w + (4 if unit else 0) + unit_w
            # Shrink until value+unit fits
            while block_w > max_text_w and val_size > 14:
                val_size -= 2
                val_font = load_font(val_size, bold=True)
                unit_font = load_font(max(13, val_size // 2))
                val_w = int(draw.textlength(text, font=val_font))
                unit_w = int(draw.textlength(unit, font=unit_font)) if unit else 0
                block_w = val_w + (4 if unit else 0) + unit_w
            # Center label
            lbl_w = int(draw.textlength(label, font=label_font))
            draw.text((cx - lbl_w // 2, y0 + 4), label, font=label_font, fill="#a0b4c8")
            # Center value+unit block
            val_x = cx - block_w // 2
            draw.text((val_x, y0 + 20), text, font=val_font, fill=value_color)
            if unit:
                unit_y = y0 + 20 + val_size - int(unit_font.size) - 2
                draw.text((val_x + val_w + 4, unit_y), unit, font=unit_font, fill="#a0b4c8")

    def _draw_cell_separators(
        self,
        draw: ImageDraw.ImageDraw,
        cells: list[tuple[int, int, int, int, bool]],
    ) -> None:
        """Draw separator lines between cells."""
        seen_hy: set[int] = set()
        seen_vx: set[tuple[int, int, int]] = set()
        for x0, y0, x1, y1, _ in cells:
            if y0 > ITEMS_Y0 and y0 not in seen_hy:
                draw.line([0, y0, WIDTH - 1, y0], fill="#1e1e2e", width=1)
                seen_hy.add(y0)
            if x0 > 0:
                key = (x0, y0, y1)
                if key not in seen_vx:
                    draw.line([x0, y0, x0, y1 - 1], fill="#1e1e2e", width=1)
                    seen_vx.add(key)

    def _format_value(self, value: object, fmt: str) -> str:
        if value is None:
            return "---"
        try:
            return fmt.format(value)
        except (ValueError, TypeError):
            return str(value)
