from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from notation_service import create_app

FIXTURES = Path(__file__).parent / "fixtures"


def read_text(path: Path) -> str:
    """UTF-8 text with line endings normalized, so expectations hold on Windows too."""
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / "input" / name).read_bytes()


@pytest.fixture
def app() -> Flask:
    return create_app()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
