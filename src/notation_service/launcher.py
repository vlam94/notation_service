"""What the desktop icon runs: start the server if needed, then open the browser."""

import http.client
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from enum import Enum, auto

from notation_service.config import APP_NAME, Config, log_file

DIALOG_TITLE = "Colinha converter"
PROBE_TIMEOUT_SECONDS = 3.0  # above the ~2 s Windows takes to refuse a connection on localhost
START_TIMEOUT_SECONDS = 15.0
POLL_INTERVAL_SECONDS = 0.25
SERVER_FLAG = "--server"


class PortState(Enum):
    OURS = auto()
    OTHER = auto()
    FREE = auto()


def port_taken_message(port: int) -> str:
    return (
        f"Another program is using port {port}. Close it, or restart the computer, and try again."
    )


def not_started_message() -> str:
    return f"The converter didn't start. Details were saved to {log_file()}."


def probe(port: int) -> PortState:
    """Who, if anyone, is answering on the port."""
    url = f"http://127.0.0.1:{port}/healthz"
    try:
        with urllib.request.urlopen(url, timeout=PROBE_TIMEOUT_SECONDS) as response:
            body = json.load(response)
    except urllib.error.HTTPError:
        return PortState.OTHER
    except OSError:  # refused, timed out, or dropped: nothing usable is listening
        return PortState.FREE
    except (http.client.HTTPException, ValueError):  # answered, but not with HTTP or JSON
        return PortState.OTHER
    is_ours = isinstance(body, dict) and body.get("app") == APP_NAME
    return PortState.OURS if is_ours else PortState.OTHER


def server_command() -> list[str]:
    # A PyInstaller build has no `python -m`; the same executable serves when given the flag.
    if getattr(sys, "frozen", False):
        return [sys.executable, SERVER_FLAG]
    return [sys.executable, "-m", "notation_service.server"]


def spawn_server() -> subprocess.Popen[bytes]:
    """Start the server detached from this process, with no console window."""
    if sys.platform == "win32":
        creationflags, new_session = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            False,
        )
    else:
        creationflags, new_session = 0, True
    return subprocess.Popen(
        server_command(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        start_new_session=new_session,
    )


def wait_until_up(port: int) -> PortState:
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        state = probe(port)
        if state is not PortState.FREE:
            return state
        time.sleep(POLL_INTERVAL_SECONDS)
    return PortState.FREE


def show_error(message: str) -> None:
    """A native dialog, since the icon has no console to print to."""
    import tkinter
    from tkinter import messagebox

    root = tkinter.Tk()
    root.withdraw()
    messagebox.showerror(DIALOG_TITLE, message)
    root.destroy()


def launch(port: int) -> int:
    """Attach to a running server or start one, then open the page; the exit code."""
    state = probe(port)
    if state is PortState.FREE:
        spawn_server()
        state = wait_until_up(port)
    if state is PortState.OURS:
        webbrowser.open(f"http://127.0.0.1:{port}/")
        return 0
    show_error(port_taken_message(port) if state is PortState.OTHER else not_started_message())
    return 1


def main() -> int:
    """Entry point of the desktop icon."""
    if SERVER_FLAG in sys.argv[1:]:
        from notation_service import server

        return server.main()
    return launch(Config.from_env().port)
