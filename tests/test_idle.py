import logging
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask

from notation_service import server
from notation_service.idle import IdleWatchdog, watch_requests


def test_fires_after_timeout() -> None:
    fired = threading.Event()
    IdleWatchdog(0.05, fired.set).reset()
    assert fired.wait(timeout=2)


def test_reset_postpones_and_cancel_stops() -> None:
    fired = threading.Event()
    watchdog = IdleWatchdog(0.3, fired.set)
    watchdog.reset()
    time.sleep(0.2)
    watchdog.reset()
    time.sleep(0.2)
    assert not fired.is_set(), "reset should have restarted the countdown"
    watchdog.cancel()
    assert not fired.wait(timeout=0.5)


@pytest.mark.parametrize(
    ("path", "counts"),
    [
        pytest.param("/", True, id="page"),
        pytest.param("/healthz", False, id="launcher-probe"),
        pytest.param("/static/app.css", False, id="asset"),
    ],
)
def test_only_a_person_using_the_app_counts_as_activity(
    app: Flask, path: str, counts: bool
) -> None:
    resets: list[None] = []

    class Recorder(IdleWatchdog):
        def reset(self) -> None:
            resets.append(None)

    watch_requests(app, Recorder(60, lambda: None))
    app.test_client().get(path)
    assert bool(resets) is counts


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@pytest.fixture
def log_in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    log = tmp_path / "logs" / "server.log"
    monkeypatch.setattr(server, "log_file", lambda: log)
    root = logging.getLogger()
    before = list(root.handlers)
    yield log
    # Close the server's log handler, or Windows cannot delete tmp_path.
    for handler in set(root.handlers) - set(before):
        root.removeHandler(handler)
        handler.close()


def test_server_shuts_itself_down_when_idle(
    log_in_tmp: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NOTATION_PORT", str(free_port()))
    monkeypatch.setenv("NOTATION_IDLE_MINUTES", "0.01")
    started = time.monotonic()
    assert server.main() == 0
    assert time.monotonic() - started < 10
    assert log_in_tmp.exists()


def test_server_exits_when_port_is_taken(log_in_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        monkeypatch.setenv("NOTATION_PORT", str(sock.getsockname()[1]))
        assert server.main() == 1
