"""Renderers turning a parsed song into colinha text, one per dialect."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from notation_service.model import Note, Song

SOLFEGE_NAMES = {"C": "dó", "D": "ré", "E": "mi", "F": "fá", "G": "sol", "A": "lá", "B": "sí"}
SECTION_SEPARATOR = "\n\n"
MEASURE_SEPARATOR = " | "

Renderer = Callable[[Song, int], str]


@dataclass(frozen=True)
class Dialect:
    label: str
    render: Renderer


def accidental(alter: int, flat: str) -> str:
    """The accidental suffix for an `alter` value; double accidentals repeat the sign."""
    return flat * -alter if alter < 0 else "#" * alter


def solfege_name(note: Note, base_octave: int) -> str:
    """One note in solfège, octave carried by casing relative to the base octave."""
    name = SOLFEGE_NAMES[note.step] + accidental(note.alter, "♭")
    above = note.octave - base_octave
    if above <= 0:
        return name
    if above == 1:
        return name.capitalize()
    return name.upper()


def letter_name(note: Note, base_octave: int) -> str:
    """One note as a letter, octave carried by one arrow per octave away from the base."""
    shift = note.octave - base_octave
    arrows = "↑" * shift if shift > 0 else "↓" * -shift
    return note.step + accidental(note.alter, "b") + arrows


def with_title(song: Song, body: Sequence[str]) -> str:
    lines = [song.title, *body] if song.title is not None else list(body)
    return "\n".join(lines)


def render_solfege(song: Song, base_octave: int) -> str:
    """One measure per line, notes in solfège separated by single spaces."""
    lines = [" ".join(solfege_name(n, base_octave) for n in m.notes) for m in song.measures]
    return with_title(song, lines)


def render_letters(song: Song, base_octave: int) -> str:
    """All measures on one line, joined by ` | `, notes as letters with octave arrows."""
    bars = MEASURE_SEPARATOR.join(
        " ".join(letter_name(n, base_octave) for n in m.notes) for m in song.measures
    )
    # An all-rest measure leaves an empty bar; collapsing keeps it visible as "| |".
    return with_title(song, [" ".join(bars.split())] if song.measures else [])


DIALECTS: dict[str, Dialect] = {
    "solfege": Dialect("Solfège (dó ré mi)", render_solfege),
    "letters": Dialect("Letters (C D E)", render_letters),
}
DEFAULT_DIALECT = next(iter(DIALECTS))


def render_colinha(songs: Sequence[Song], dialect: Dialect, base_octave: int) -> str:
    """The whole colinha: every section rendered, separated by a blank line."""
    return SECTION_SEPARATOR.join(dialect.render(song, base_octave) for song in songs)
