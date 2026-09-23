"""Serves the app on 127.0.0.1 with waitress until it has been idle long enough."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from waitress.server import create_server

from notation_service import create_app
from notation_service.config import Config, log_file
from notation_service.idle import IdleWatchdog, watch_requests

HOST = "127.0.0.1"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUPS = 2

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    path = log_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])


def ensure_stderr() -> None:
    # A windowless process has no stderr; music21 writes its warnings there and would crash.
    if sys.stderr is None:
        sys.stderr = Path(os.devnull).open("w", encoding="utf-8")  # noqa: SIM115


def main() -> int:
    """Serve until idle; exit non-zero if the port cannot be taken."""
    ensure_stderr()
    configure_logging()
    config = Config.from_env()
    app = create_app(config)
    try:
        server = create_server(app, host=HOST, port=config.port)
    except OSError:
        logger.exception("Could not listen on %s:%s", HOST, config.port)
        return 1
    watchdog = IdleWatchdog(config.idle_minutes * 60, server.close)
    watch_requests(app, watchdog)
    watchdog.reset()
    logger.info(
        "Serving on http://%s:%s/, idle timeout %s min", HOST, config.port, config.idle_minutes
    )
    server.run()
    logger.info("Idle for %s min; shut down", config.idle_minutes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
