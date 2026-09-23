import pytest

from notation_service.config import Config, log_file


def test_defaults() -> None:
    config = Config.from_env({})
    assert (config.port, config.idle_minutes, config.max_upload_mb) == (5117, 20, 10)
    assert config.max_upload_bytes == 10 * 1024 * 1024


def test_reads_environment() -> None:
    env = {"NOTATION_PORT": "6000", "NOTATION_IDLE_MINUTES": "0.25", "NOTATION_MAX_UPLOAD_MB": "2"}
    assert Config.from_env(env) == Config(port=6000, idle_minutes=0.25, max_upload_mb=2)


@pytest.mark.parametrize(
    "env",
    [
        {"NOTATION_PORT": "abc"},
        {"NOTATION_PORT": "70000"},
        {"NOTATION_IDLE_MINUTES": "-1"},
        {"NOTATION_MAX_UPLOAD_MB": "lots"},
    ],
)
def test_bad_values_fall_back_to_defaults(
    env: dict[str, str], caplog: pytest.LogCaptureFixture
) -> None:
    assert Config.from_env(env) == Config()
    assert "Ignoring" in caplog.text


def test_log_file_is_per_user_and_not_nested_twice() -> None:
    path = log_file()
    assert path.name == "server.log"
    assert path.parts.count("notation_service") == 1
