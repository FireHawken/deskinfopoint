from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from .config import HaConfig, SubscriptionConfig
from .state import SharedState

logger = logging.getLogger(__name__)


def prefetch(ha: HaConfig, subscriptions: list[SubscriptionConfig], state: SharedState) -> None:
    """Seed SharedState with current HA entity states before the first render.

    Called once at startup for every subscription that has entity_id set.
    Failures are logged as warnings and never crash the app — MQTT will
    populate the values when the next sensor update arrives.
    """
    eligible = [s for s in subscriptions if s.entity_id]
    if not eligible:
        return

    logger.info("Prefetching %d HA state(s) from %s", len(eligible), ha.url)
    for sub in eligible:
        url = f"{ha.url}/api/states/{sub.entity_id}"
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {ha.token}"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            raw = str(data["state"])
            if raw in ("unknown", "unavailable"):
                logger.debug("HA prefetch: %s is %s — skipping", sub.entity_id, raw)
                continue
            try:
                value: float | str = float(raw)
            except ValueError:
                value = raw
            state.update_mqtt(sub.id, value)
            logger.info("HA prefetch: %s → %s = %r", sub.entity_id, sub.id, value)
        except urllib.error.URLError as e:
            logger.warning("HA prefetch failed for %s: %s", sub.entity_id, e)
        except (KeyError, json.JSONDecodeError) as e:
            logger.warning("HA prefetch: unexpected response for %s: %s", sub.entity_id, e)
