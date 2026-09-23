"""Settings read once from the environment."""

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_log_dir

APP_NAME = "notation_service"
DEFAULT_PORT = 5117
DEFAULT_IDLE_MINUTES = 20.0
DEFAULT_MAX_UPLOAD_MB = 10.0
ALLOWED_SUFFIXES = frozenset({".xml", ".musicxml", ".mxl"})

logger = logging.getLogger(__name__)


def log_file() -> Path:
    """The server log; on Windows %LOCALAPPDATA%\\notation_service\\Logs\\server.log."""
    # appauthor=False, or Windows nests the app name twice: notation_service\notation_service.
    return Path(user_log_dir(APP_NAME, appauthor=False)) / "server.log"


@dataclass(frozen=True)
class Config:
    port: int = DEFAULT_PORT
    idle_minutes: float = DEFAULT_IDLE_MINUTES
    max_upload_mb: float = DEFAULT_MAX_UPLOAD_MB
    allowed_suffixes: frozenset[str] = ALLOWED_SUFFIXES

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb * 1024 * 1024)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Config":
        """Build from NOTATION_* variables; a bad value falls back to the default with a warning."""
        env = os.environ if env is None else env
        return cls(
            port=read_setting(env, "NOTATION_PORT", int, DEFAULT_PORT, lambda v: 0 < v < 65536),
            idle_minutes=read_setting(
                env, "NOTATION_IDLE_MINUTES", float, DEFAULT_IDLE_MINUTES, lambda v: v > 0
            ),
            max_upload_mb=read_setting(
                env, "NOTATION_MAX_UPLOAD_MB", float, DEFAULT_MAX_UPLOAD_MB, lambda v: v > 0
            ),
        )


def read_setting[T: (int, float)](
    env: Mapping[str, str],
    name: str,
    parse: Callable[[str], T],
    default: T,
    valid: Callable[[T], bool],
) -> T:
    raw = env.get(name)
    if raw is None:
        return default
    try:
        value = parse(raw)
    except ValueError:
        value = None
    if value is None or not valid(value):
        logger.warning("Ignoring %s=%r; using the default %s", name, raw, default)
        return default
    return value
