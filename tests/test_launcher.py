import json
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from notation_service import launcher
from notation_service.launcher import PortState


class Launch:
    """Records what the launcher did instead of opening browsers and dialogs."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.opened: list[str] = []
        self.errors: list[str] = []
        self.spawned: list[subprocess.Popen[bytes]] = []
        monkeypatch.setattr(launcher.webbrowser, "open", self.opened.append)
        monkeypatch.setattr(launcher, "show_error", self.errors.append)


@pytest.fixture
def launch(monkeypatch: pytest.MonkeyPatch) -> Launch:
    return Launch(monkeypatch)


def stub_server(status: int, body: bytes) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


OURS = (200, json.dumps({"status": "ok", "app": "notation_service"}).encode())


@pytest.fixture
def ours() -> Iterator[int]:
    server = stub_server(*OURS)
    yield server.server_port
    server.shutdown()
    server.server_close()


@pytest.fixture
def other() -> Iterator[int]:
    server = stub_server(404, b"<h1>Not Found</h1>")
    yield server.server_port
    server.shutdown()
    server.server_close()


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@pytest.mark.parametrize(
    ("status", "body", "state"),
    [
        pytest.param(*OURS, PortState.OURS, id="ours"),
        pytest.param(404, b"Not Found", PortState.OTHER, id="http-error"),
        pytest.param(200, b"<html>", PortState.OTHER, id="not-json"),
        pytest.param(200, b'{"app": "other"}', PortState.OTHER, id="other-app"),
    ],
)
def test_probe(status: int, body: bytes, state: PortState) -> None:
    server = stub_server(status, body)
    try:
        assert launcher.probe(server.server_port) is state
    finally:
        server.shutdown()
        server.server_close()


def test_probe_free_port() -> None:
    assert launcher.probe(free_port()) is PortState.FREE


def test_attaches_to_running_server(
    launch: Launch, ours: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launcher, "spawn_server", pytest.fail)
    assert launcher.launch(ours) == 0
    assert launch.opened == [f"http://127.0.0.1:{ours}/"]


def test_spawns_when_none_is_running(launch: Launch, monkeypatch: pytest.MonkeyPatch) -> None:
    servers: list[ThreadingHTTPServer] = []
    monkeypatch.setattr(launcher, "probe", lambda _: PortState.OURS if servers else PortState.FREE)
    monkeypatch.setattr(launcher, "spawn_server", lambda: servers.append(stub_server(*OURS)))
    assert launcher.launch(5117) == 0
    assert len(servers) == 1
    assert launch.opened == ["http://127.0.0.1:5117/"]
    servers[0].shutdown()
    servers[0].server_close()


@pytest.mark.parametrize(
    ("form", "message"),
    [
        pytest.param(
            "port_taken",
            "Another program is using port {port}. Close it, or restart the computer, "
            "and try again.",
            id="E13",
        ),
        pytest.param(
            "never_starts",
            "The converter didn't start. Details were saved to {log}.",
            id="E14",
        ),
    ],
)
def test_error_catalogue(
    launch: Launch,
    other: int,
    monkeypatch: pytest.MonkeyPatch,
    form: str,
    message: str,
) -> None:
    port = other if form == "port_taken" else free_port()
    monkeypatch.setattr(launcher, "spawn_server", lambda: None)
    monkeypatch.setattr(launcher, "START_TIMEOUT_SECONDS", 0.5)
    assert launcher.launch(port) == 1
    assert launch.errors == [message.format(port=port, log=launcher.log_file())]
    assert launch.opened == []


def test_server_command_for_a_frozen_build(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert launcher.server_command() == [sys.executable, launcher.SERVER_FLAG]


def test_frozen_build_serves_when_given_the_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from notation_service import server

    monkeypatch.setattr(sys, "argv", ["notation-service", launcher.SERVER_FLAG])
    monkeypatch.setattr(server, "main", lambda: 7)
    assert launcher.main() == 7


def test_real_spawn_attach_and_idle_exit(
    launch: Launch, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End to end on this platform: the detached spawn branch, attach, and idle shutdown."""
    port = free_port()
    monkeypatch.setenv("NOTATION_PORT", str(port))
    monkeypatch.setenv("NOTATION_IDLE_MINUTES", "0.05")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))  # keep the log out of the real one on Linux
    monkeypatch.setattr(sys, "argv", ["notation-service"])
    real_spawn = launcher.spawn_server

    def recording_spawn() -> subprocess.Popen[bytes]:
        process = real_spawn()
        launch.spawned.append(process)
        return process

    monkeypatch.setattr(launcher, "spawn_server", recording_spawn)
    try:
        assert launcher.main() == 0, launch.errors
        assert launcher.main() == 0, "second click should attach"
        assert len(launch.spawned) == 1
        assert launch.opened == [f"http://127.0.0.1:{port}/"] * 2
        assert launch.spawned[0].wait(timeout=60) == 0, "server should exit when idle"
    finally:
        for process in launch.spawned:
            process.kill()
            process.wait()
