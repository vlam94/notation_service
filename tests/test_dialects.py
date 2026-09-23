import pytest

from notation_service.dialects import (
    DIALECTS,
    Renderer,
    letter_name,
    render_colinha,
    render_letters,
    render_solfege,
    solfege_name,
)
from notation_service.model import Measure, Note, Song

BASE = 2


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        pytest.param(Note("B", 2, -1), "sí♭", id="flat"),
        pytest.param(Note("F", 2, 1), "fá#", id="sharp-defect-1"),
        pytest.param(Note("C", 2, 0), "dó", id="natural"),
        pytest.param(Note("E", 2, -2), "mi♭♭", id="double-flat"),
        pytest.param(Note("G", 2, 0), "sol", id="base-lowercase"),
        pytest.param(Note("G", 3, 0), "Sol", id="base+1-title"),
        pytest.param(Note("B", 3, -1), "Sí♭", id="base+1-title-flat"),
        pytest.param(Note("G", 4, 0), "SOL", id="base+2-upper"),
        pytest.param(Note("B", 6, -1), "SÍ♭", id="base+4-upper"),
        pytest.param(Note("A", 1, 0), "lá", id="below-base-lowercase"),
    ],
)
def test_solfege_name(note: Note, expected: str) -> None:
    assert solfege_name(note, BASE) == expected


@pytest.mark.parametrize(
    ("note", "expected"),
    [
        pytest.param(Note("A", 2, -1), "Ab", id="flat"),
        pytest.param(Note("F", 2, 1), "F#", id="sharp"),
        pytest.param(Note("B", 3, -1), "Bb↑", id="one-above"),
        pytest.param(Note("C", 4, 0), "C↑↑", id="two-above"),
        pytest.param(Note("D", 1, 0), "D↓", id="one-below"),
    ],
)
def test_letter_name(note: Note, expected: str) -> None:
    assert letter_name(note, BASE) == expected


def measure(*notes: Note) -> Measure:
    return Measure(notes)


SONG = Song(
    "Love story",
    (
        measure(Note("F", 2, 0), Note("F", 3, 0)),
        measure(),  # all rests
        measure(Note("A", 3, -1), Note("B", 4, -1)),
    ),
)


@pytest.mark.parametrize(
    ("song", "render", "expected"),
    [
        pytest.param(SONG, render_solfege, "Love story\nfá Fá\n\nLá♭ SÍ♭", id="solfege"),
        pytest.param(SONG, render_letters, "Love story\nF F↑ | | Ab↑ Bb↑↑", id="letters"),
        pytest.param(Song(None, (measure(Note("C", 2, 0)),)), render_solfege, "dó", id="untitled"),
        pytest.param(Song(None, ()), render_solfege, "", id="empty-solfege"),
        pytest.param(Song(None, ()), render_letters, "", id="empty-letters"),
        pytest.param(Song("A", ()), render_letters, "A", id="title-only"),
    ],
)
def test_render(song: Song, render: Renderer, expected: str) -> None:
    assert render(song, BASE) == expected


def test_letters_matches_documented_example() -> None:
    song = Song(
        None,
        (
            measure(Note("A", 2, -1), Note("G", 2, 0)),
            measure(Note("F", 2, 0)),
            measure(Note("B", 3, -1), Note("E", 2, -1)),
            measure(Note("F", 2, 0)),
        ),
    )
    assert render_letters(song, BASE) == "Ab G | F | Bb↑ Eb | F"


def test_render_colinha_separates_sections_with_a_blank_line() -> None:
    songs = [Song(None, (measure(Note("C", 2, 0)),)), Song("B", (measure(Note("D", 2, 0)),))]
    assert render_colinha(songs, DIALECTS["solfege"], BASE) == "dó\n\nB\nré"


def test_every_dialect_has_a_label() -> None:
    assert all(d.label for d in DIALECTS.values())
