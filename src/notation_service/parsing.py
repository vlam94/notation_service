"""Reads a MusicXML file with music21 and turns it into model objects.

Every failure music21 can raise is converted here into a `ScoreError` carrying the user-facing
message from the error catalogue in PLAN.md, so no other module imports music21.
"""

import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from xml.etree.ElementTree import ParseError

from music21 import chord, converter, exceptions21, expressions, note, stream

from notation_service.model import Measure, Note, Part, Song

# The first bytes of an XML document (optionally after a BOM) or of a zip (.mxl) container.
SCORE_CONTAINER_SIGNATURES = (b"<", b"PK")
UTF8_BOM = b"\xef\xbb\xbf"
DEFAULT_BASE_OCTAVE = 4


class ScoreError(Exception):
    """A problem with the user's input, carrying the message to show them."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def not_a_score_message(filename: str) -> str:
    return f"“{filename}” doesn't contain a score. Check it is the file exported from MuseScore."


def damaged_message(filename: str) -> str:
    return f"“{filename}” seems to be damaged. Try exporting it from MuseScore again."


def no_notes_message(filename: str, instrument: str) -> str:
    return (
        f"“{filename}” has no notes to write out for “{instrument}”. "
        "Choose another instrument or file."
    )


def looks_like_score_container(path: Path) -> bool:
    """Whether the file at least starts like XML or a zip, i.e. is damaged rather than foreign."""
    with path.open("rb") as file:
        head = file.read(64).removeprefix(UTF8_BOM).lstrip()
    return head.startswith(SCORE_CONTAINER_SIGNATURES)


def load_score(path: Path, filename: str) -> stream.Score:
    try:
        # forceSource stops music21 caching a pickle of the upload in the temp directory.
        parsed = converter.parse(path, forceSource=True)
    except (ParseError, zipfile.BadZipFile) as exc:
        message = damaged_message if looks_like_score_container(path) else not_a_score_message
        raise ScoreError(message(filename)) from exc
    except exceptions21.Music21Exception as exc:
        raise ScoreError(not_a_score_message(filename)) from exc
    if not isinstance(parsed, stream.Score) or not parsed.parts:
        raise ScoreError(not_a_score_message(filename))
    return parsed


def is_tied_into(general_note: note.NotRest) -> bool:
    """A note held over from the previous one is struck once, so only the tie's start counts."""
    return general_note.tie is not None and general_note.tie.type in {"stop", "continue"}


def to_note(general_note: note.NotRest) -> Note | None:
    if isinstance(general_note, note.Note):
        pitch = general_note.pitch
    elif isinstance(general_note, chord.Chord) and general_note.pitches:
        # The parts this app is for are single-line; for the odd chord, the lowest note stands in.
        pitch = min(general_note.pitches)
    else:  # unpitched percussion has no name to write out
        return None
    return Note(step=pitch.step, octave=pitch.implicitOctave, alter=int(pitch.alter))


def to_measure(measure: stream.Measure) -> Measure:
    # flatten() so notes in a second voice are included, in time order.
    candidates = (n for n in measure.flatten().notes if not is_tied_into(n))
    return Measure(tuple(n for n in map(to_note, candidates) if n is not None))


def rehearsal_mark(measure: stream.Measure) -> str | None:
    mark = measure.getElementsByClass(expressions.RehearsalMark).first()
    return None if mark is None else str(mark.content)


def split_sections(part: stream.Part) -> Iterator[Song]:
    """Group measures into songs, a new one starting at each rehearsal mark."""
    title: str | None = None
    measures: list[Measure] = []
    for measure in part.getElementsByClass(stream.Measure):
        mark = rehearsal_mark(measure)
        if mark is not None:
            if measures or title is not None:
                yield Song(title, tuple(measures))
            title, measures = mark, []
        measures.append(to_measure(measure))
    if measures or title is not None:
        yield Song(title, tuple(measures))


def to_part(part: stream.Part, number: int) -> Part:
    name = part.partName or f"Instrument {number}"
    return Part(name=str(name), songs=tuple(split_sections(part)))


def parse_score(path: Path, filename: str | None = None) -> tuple[Part, ...]:
    """Every instrument in the score at `path`; `filename` is the name the user knows it by."""
    score = load_score(path, filename or path.name)
    return tuple(to_part(p, i) for i, p in enumerate(score.parts, start=1))


def require_notes(part: Part, filename: str) -> None:
    """Refuse a part with nothing to write out — only rests, or only percussion."""
    if not part.notes():
        raise ScoreError(no_notes_message(filename, part.name))


def detect_base_octave(songs: Sequence[Song]) -> int:
    """The octave of the lowest note, so that note renders in the lowest casing tier."""
    octaves = (n.octave for s in songs for m in s.measures for n in m.notes)
    return min(octaves, default=DEFAULT_BASE_OCTAVE)
