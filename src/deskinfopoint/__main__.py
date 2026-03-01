from __future__ import annotations

import argparse
import fcntl
import logging
import os
import sys
from pathlib import Path

from .config import ConfigError, load_config
from .app import App

_LOCK_PATH = "/tmp/deskinfopoint.lock"


def _acquire_lock():
    """Open and exclusively lock _LOCK_PATH.  Returns the open file object
    (must stay alive for the duration of the process — the OS releases the
    lock automatically when the file descriptor is closed or the process exits).
    Exits with a clear error if another instance already holds the lock.
    """
    # Open without truncating so the existing PID is readable on lock failure.
    lock_file = open(_LOCK_PATH, "a+")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.seek(0)
        pid = lock_file.read().strip()
        lock_file.close()
        pid_info = f" (PID {pid})" if pid else ""
        print(
            f"deskinfopoint is already running{pid_info}.\n"
            f"Stop the existing instance before starting a new one.",
            file=sys.stderr,
        )
        sys.exit(1)
    # Lock acquired — write our PID.
    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


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

    _lock = _acquire_lock()  # noqa: F841 — kept alive to hold the OS lock
    state_file = str(Path(args.config).resolve().parent / "state.json")
    App(config, state_file).run()


if __name__ == "__main__":
    main()
