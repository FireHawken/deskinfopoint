from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def load(path: str) -> dict:
    """Load persisted state from *path*.  Returns {} on missing file or any error."""
    try:
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("Could not read state file %s: %s", path, e)
    return {}


def save(path: str, screen: int, brightness: float, led_brightness: float = 1.0) -> None:
    """Atomically write screen index, brightness, and LED brightness to *path*."""
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(
                {"screen": screen, "brightness": brightness, "led_brightness": led_brightness},
                f,
            )
        os.replace(tmp, path)
    except Exception as e:
        logger.warning("Could not save state file %s: %s", path, e)
