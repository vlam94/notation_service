"""The parsed score, independent of music21 and of how it is rendered."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Note:
    step: str  # "C".."B"
    octave: int
    alter: int  # -1 flat, 0 natural, 1 sharp


@dataclass(frozen=True)
class Measure:
    notes: tuple[Note, ...]


@dataclass(frozen=True)
class Song:
    title: str | None  # the rehearsal mark, or None for a leading section
    measures: tuple[Measure, ...]


@dataclass(frozen=True)
class Part:
    name: str
    songs: tuple[Song, ...]

    def notes(self) -> tuple[Note, ...]:
        """Every note in the part, in score order."""
        return tuple(n for s in self.songs for m in s.measures for n in m.notes)
