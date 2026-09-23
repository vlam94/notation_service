"""Shuts the server down once nobody has used it for a while."""

import threading
from collections.abc import Callable

from flask import Flask, request

# Requests that are not a person using the app: the launcher's probe and page assets.
UNWATCHED_PREFIXES = ("/healthz", "/static/")


class IdleWatchdog:
    """Calls `on_idle` once `timeout_seconds` pass without a `reset`."""

    def __init__(self, timeout_seconds: float, on_idle: Callable[[], None]) -> None:
        self._timeout_seconds = timeout_seconds
        self._on_idle = on_idle
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def reset(self) -> None:
        """Restart the countdown."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self._timeout_seconds, self._on_idle)
            self._timer.daemon = True
            self._timer.start()

    def cancel(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()


def watch_requests(app: Flask, watchdog: IdleWatchdog) -> None:
    """Reset the watchdog on every request a person makes."""

    @app.before_request
    def record_activity() -> None:
        if not request.path.startswith(UNWATCHED_PREFIXES):
            watchdog.reset()
