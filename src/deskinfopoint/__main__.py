from __future__ import annotations

import argparse
import logging
import sys

from .config import ConfigError, load_config
from .app import App


def main() -> None:
    parser = argparse.ArgumentParser(
        description="deskinfopoint — display sensor and MQTT data on a DIY device"
    )
    parser.add_argument(
        "--config", default="config.yaml", metavar="PATH",
        help="path to config YAML (default: config.yaml)"
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="logging verbosity (default: INFO)"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)-24s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"Config file not found: {args.config}", file=sys.stderr)
        sys.exit(1)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    App(config).run()


if __name__ == "__main__":
    main()
