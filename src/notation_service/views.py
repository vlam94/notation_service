"""The upload form and the conversion it drives."""

import logging
import tempfile
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, current_app, render_template, request
from flask.typing import ResponseReturnValue
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException

from notation_service.config import APP_NAME, Config
from notation_service.dialects import DEFAULT_DIALECT, DIALECTS, render_colinha
from notation_service.model import Part
from notation_service.parsing import ScoreError, detect_base_octave, parse_score, require_notes

MUSESCORE_SUFFIXES = frozenset({".mscz", ".mscx"})
OCTAVE_RANGE = range(0, 9)
AUTOMATIC = "auto"

bp = Blueprint("main", __name__)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Choices:
    """What the user picked on the form, kept as submitted so a failed conversion can show it."""

    dialect: str = DEFAULT_DIALECT
    octave: str = AUTOMATIC
    part: str = "0"

    @classmethod
    def from_form(cls, form: Mapping[str, str]) -> "Choices":
        dialect = form.get("dialect", DEFAULT_DIALECT)
        return cls(
            dialect=dialect if dialect in DIALECTS else DEFAULT_DIALECT,
            octave=form.get("octave", AUTOMATIC),
            part=form.get("part", "0"),
        )


@dataclass(frozen=True)
class Result:
    filename: str
    instrument: str
    colinha: str

    @property
    def download_name(self) -> str:
        return f"{Path(self.filename).stem} - colinha.txt"


def page(
    choices: Choices,
    *,
    parts: Sequence[Part] = (),
    result: Result | None = None,
    error: str | None = None,
) -> str:
    return render_template(
        "index.html",
        dialects=DIALECTS,
        octaves=OCTAVE_RANGE,
        automatic=AUTOMATIC,
        choices=choices,
        parts=parts,
        result=result,
        error=error,
    )


def check_file_type(filename: str, allowed_suffixes: frozenset[str]) -> None:
    if not filename:
        raise ScoreError("Choose a score file first — the one you exported from MuseScore.")
    suffix = Path(filename).suffix.lower()
    if suffix in MUSESCORE_SUFFIXES:
        raise ScoreError(
            f"“{filename}” is a MuseScore project. In MuseScore use File → Export → MusicXML, "
            "then upload the exported file."
        )
    if suffix not in allowed_suffixes:
        raise ScoreError(
            f"“{filename}” isn't a score file this app can read. Export the score from MuseScore "
            "as MusicXML (.musicxml, .xml or .mxl)."
        )


def check_file_size(path: Path, filename: str, config: Config) -> None:
    size = path.stat().st_size
    if size == 0:
        raise ScoreError(f"“{filename}” is empty. Try exporting it again.")
    if size > config.max_upload_bytes:
        raise ScoreError(
            f"“{filename}” is larger than {config.max_upload_mb:g} MB, which is more than any "
            "single score should be. Check that it is the right file."
        )


def base_octave_override(raw: str) -> int | None:
    """The octave chosen on the form, or None for automatic detection."""
    if raw == AUTOMATIC:
        return None
    octave = int(raw) if raw.isdecimal() else -1
    if octave not in OCTAVE_RANGE:
        raise ScoreError(f"Base octave must be between {OCTAVE_RANGE[0]} and {OCTAVE_RANGE[-1]}.")
    return octave


def chosen_part(parts: Sequence[Part], raw: str) -> Part:
    # A single-instrument file has only one answer, whatever a previous file left selected.
    if len(parts) == 1:
        return parts[0]
    index = int(raw) if raw.isdecimal() else -1
    if index >= len(parts) or index < 0:
        raise ScoreError(f"This file has {len(parts)} instruments; choose one from the list.")
    return parts[index]


@contextmanager
def saved_upload(upload: FileStorage, suffix: str) -> Iterator[Path]:
    """The upload as a closed temp file, removed afterwards.

    Closed before use because Windows cannot reopen a still-open temp file by name.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)  # noqa: SIM115
    path = Path(tmp.name)
    try:
        with tmp:
            upload.save(tmp)
        yield path
    finally:
        path.unlink(missing_ok=True)


def uploaded_filename() -> str:
    upload = request.files.get("score")
    return (upload.filename or "") if upload else ""


@bp.get("/")
def index() -> ResponseReturnValue:
    return page(Choices())


@bp.post("/")
def convert() -> ResponseReturnValue:
    config: Config = current_app.config["NOTATION"]
    choices = Choices.from_form(request.form)
    filename = uploaded_filename()
    parts: tuple[Part, ...] = ()
    try:
        check_file_type(filename, config.allowed_suffixes)
        override = base_octave_override(choices.octave)
        with saved_upload(request.files["score"], Path(filename).suffix.lower()) as path:
            check_file_size(path, filename, config)
            parts = parse_score(path, filename)
        part = chosen_part(parts, choices.part)
        require_notes(part, filename)
    except ScoreError as exc:
        logger.info("Refused %r: %s", filename, exc.message, exc_info=exc.__cause__)
        return page(choices, parts=parts, error=exc.message), 400
    base_octave = detect_base_octave(part.songs) if override is None else override
    colinha = render_colinha(part.songs, DIALECTS[choices.dialect], base_octave)
    return page(choices, parts=parts, result=Result(filename, part.name, colinha))


@bp.get("/healthz")
def healthz() -> ResponseReturnValue:
    return {"status": "ok", "app": APP_NAME}


@bp.app_errorhandler(Exception)
def unexpected_error(exc: Exception) -> ResponseReturnValue:
    """The one catch-all: a friendly page for the user, the traceback for the log."""
    if isinstance(exc, HTTPException):
        return exc
    filename = uploaded_filename()
    logger.exception("Unexpected error converting %r", filename)
    subject = f"converting “{filename}”" if filename else "here"
    message = f"Something went wrong {subject}. It has been logged."
    return page(Choices.from_form(request.form), error=message), 500
