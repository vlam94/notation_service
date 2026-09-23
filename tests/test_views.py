import html as html_escaping
import io
import logging
import re
import tempfile
from pathlib import Path
from typing import Any

import pytest
from flask.testing import FlaskClient
from werkzeug.test import TestResponse

from notation_service import views
from tests.conftest import FIXTURES, fixture_bytes, read_text

TEN_MB = 10 * 1024 * 1024
KEPT_CHOICES = {"dialect": "letters", "octave": "3"}


def upload(client: FlaskClient, content: bytes, filename: str, **form: str) -> TestResponse:
    data: dict[str, Any] = {"score": (io.BytesIO(content), filename), **form}
    return client.post("/", data=data, content_type="multipart/form-data")


def html(response: TestResponse) -> str:
    return response.get_data(as_text=True)


def colinha(response: TestResponse) -> str:
    match = re.search(r'<pre id="colinha">(.*?)</pre>', html(response), re.DOTALL)
    assert match, "no colinha on the page"
    return match.group(1)


def assert_choices_kept(page: str) -> None:
    assert re.search(r'value="letters"\s+checked', page)
    assert '<option value="3" selected>' in page


def test_form_has_defaults_and_no_instrument_selector(client: FlaskClient) -> None:
    page = html(client.get("/"))
    assert re.search(r'value="solfege"\s+checked', page)
    assert "Automatic" in page
    assert 'id="part"' not in page
    assert "https://" not in page, "nothing may load from a CDN"


def test_convert_solfege(client: FlaskClient) -> None:
    response = upload(client, fixture_bytes("accidentals.xml"), "accidentals.xml")
    assert response.status_code == 200
    assert colinha(response) + "\n" == read_text(FIXTURES / "output" / "accidentals.txt")


def test_convert_letters_with_octave_override(client: FlaskClient) -> None:
    response = upload(
        client, fixture_bytes("accidentals.xml"), "accidentals.xml", dialect="letters", octave="3"
    )
    assert colinha(response) == "Accidentals\nBb↓ Eb F# C↑"
    assert_choices_kept(html(response))


def test_second_instrument_and_selector_by_name(client: FlaskClient) -> None:
    response = upload(client, fixture_bytes("two_parts.xml"), "two_parts.xml", part="1")
    page = html(response)
    assert colinha(response) == "sol Lá"
    assert '<option value="1" selected>Tuba</option>' in page
    assert "Trombone" in page


def test_stale_instrument_choice_is_ignored_for_a_single_instrument_file(
    client: FlaskClient,
) -> None:
    response = upload(client, fixture_bytes("accidentals.xml"), "accidentals.xml", part="1")
    assert response.status_code == 200


def test_unknown_dialect_falls_back_to_default(client: FlaskClient) -> None:
    response = upload(client, fixture_bytes("accidentals.xml"), "a.xml", dialect="klingon")
    assert colinha(response).startswith("Accidentals\nsí♭")


def test_download_link_is_the_colinha_as_utf8(client: FlaskClient) -> None:
    from urllib.parse import unquote

    response = upload(client, fixture_bytes("multiple_sections.xml"), "Canção de São João.xml")
    page = html(response)
    assert 'download="Canção de São João - colinha.txt"' in page
    href = re.search(r'href="data:text/plain;charset=utf-8,([^"]*)"', page)
    assert href
    assert unquote(href.group(1), encoding="utf-8") == colinha(response)


def test_healthz_identifies_the_app(client: FlaskClient) -> None:
    assert client.get("/healthz").get_json() == {"status": "ok", "app": "notation_service"}


def test_unknown_page_is_a_plain_404(client: FlaskClient) -> None:
    assert client.get("/nope").status_code == 404


def test_uploads_leave_no_temp_files(
    client: FlaskClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    upload(client, fixture_bytes("accidentals.xml"), "ok.xml")
    upload(client, fixture_bytes("truncated.xml"), "bad.xml")
    upload(client, b"", "empty.xml")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("content", "filename", "form", "status", "message"),
    [
        pytest.param(
            b"",
            "",
            KEPT_CHOICES,
            400,
            "Choose a score file first — the one you exported from MuseScore.",
            id="E01",
        ),
        pytest.param(
            b"PK\x03\x04",
            "song.mscz",
            KEPT_CHOICES,
            400,
            "“song.mscz” is a MuseScore project. In MuseScore use File → Export → MusicXML, "
            "then upload the exported file.",
            id="E02",
        ),
        pytest.param(
            b"%PDF-1.4",
            "song.pdf",
            KEPT_CHOICES,
            400,
            "“song.pdf” isn't a score file this app can read. Export the score from MuseScore "
            "as MusicXML (.musicxml, .xml or .mxl).",
            id="E03",
        ),
        pytest.param(
            b"",
            "song.xml",
            KEPT_CHOICES,
            400,
            "“song.xml” is empty. Try exporting it again.",
            id="E04",
        ),
        pytest.param(
            b" " * (TEN_MB + 1),
            "song.xml",
            KEPT_CHOICES,
            400,
            "“song.xml” is larger than 10 MB, which is more than any single score should be. "
            "Check that it is the right file.",
            id="E05",
        ),
        pytest.param(
            fixture_bytes("not_xml.xml"),
            "song.xml",
            KEPT_CHOICES,
            400,
            "“song.xml” doesn't contain a score. Check it is the file exported from MuseScore.",
            id="E06",
        ),
        pytest.param(
            fixture_bytes("truncated.xml"),
            "song.xml",
            KEPT_CHOICES,
            400,
            "“song.xml” seems to be damaged. Try exporting it from MuseScore again.",
            id="E07",
        ),
        pytest.param(
            fixture_bytes("not_a_score.xml"),
            "song.xml",
            KEPT_CHOICES,
            400,
            "“song.xml” doesn't contain a score. Check it is the file exported from MuseScore.",
            id="E08",
        ),
        pytest.param(
            fixture_bytes("only_rests.xml"),
            "song.xml",
            KEPT_CHOICES,
            400,
            "“song.xml” has no notes to write out for “Drums”. Choose another instrument or file.",
            id="E09",
        ),
        pytest.param(
            fixture_bytes("two_parts.xml"),
            "song.xml",
            {**KEPT_CHOICES, "part": "99"},
            400,
            "This file has 2 instruments; choose one from the list.",
            id="E10",
        ),
        pytest.param(
            fixture_bytes("accidentals.xml"),
            "song.xml",
            {"dialect": "letters", "octave": "42"},
            400,
            "Base octave must be between 0 and 8.",
            id="E11",
        ),
        pytest.param(
            fixture_bytes("accidentals.xml"),
            "Canção de São João 東京.xml",
            KEPT_CHOICES,
            200,
            "Canção de São João 東京.xml",
            id="E12",
        ),
    ],
)
def test_error_catalogue(
    client: FlaskClient,
    content: bytes,
    filename: str,
    form: dict[str, str],
    status: int,
    message: str,
) -> None:
    response = upload(client, content, filename, **form)
    page = html(response)
    assert response.status_code == status
    assert response.mimetype == "text/html"
    assert message in html_escaping.unescape(page)
    assert "Traceback" not in page
    assert re.search(r'value="letters"\s+checked', page)
    if form.get("octave") == "3":
        assert '<option value="3" selected>' in page


@pytest.mark.parametrize("filename", [pytest.param("song.xml", id="E15")])
def test_error_catalogue_unexpected(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    filename: str,
) -> None:
    def explode(*_: object) -> str:
        raise RuntimeError("secret internals")

    monkeypatch.setattr(views, "render_colinha", explode)
    with caplog.at_level(logging.ERROR):
        response = upload(client, fixture_bytes("accidentals.xml"), filename, **KEPT_CHOICES)
    page = html(response)
    assert response.status_code == 500
    assert f"Something went wrong converting “{filename}”. It has been logged." in page
    assert "secret internals" not in page
    assert "RuntimeError" not in page
    assert_choices_kept(page)
    assert "secret internals" in caplog.text
