from __future__ import annotations

import os
from abc import ABC, abstractmethod
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
        draw.text((10, 8), self.name, font=load_font(14, bold=True), fill="#dde6f0")

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
