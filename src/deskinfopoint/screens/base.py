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
    if row_height >= 100:
        return 56
    if row_height >= 70:
        return 40
    if row_height >= 55:
        return 32
    return 26


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

    def _format_value(self, value: object, fmt: str) -> str:
        if value is None:
            return "---"
        try:
            return fmt.format(value)
        except (ValueError, TypeError):
            return str(value)
