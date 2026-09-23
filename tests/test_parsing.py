import zipfile
from pathlib import Path

import pytest

from notation_service.dialects import DIALECTS, render_colinha
from notation_service.parsing import ScoreError, detect_base_octave, parse_score, require_notes
from tests.conftest import FIXTURES, read_text

INPUTS = sorted((FIXTURES / "input").glob("*.xml"))


def solfege_colinha(path: Path, part_index: int = 0, filename: str | None = None) -> str:
    part = parse_score(path, filename)[part_index]
    require_notes(part, filename or path.name)
    return render_colinha(part.songs, DIALECTS["solfege"], detect_base_octave(part.songs))


def expected_output(path: Path) -> Path:
    outputs = list((FIXTURES / "output").glob(f"{path.stem}.*"))
    assert len(outputs) == 1, f"{path.name} needs exactly one .txt or .error expectation"
    return outputs[0]


@pytest.mark.parametrize("path", INPUTS, ids=[p.stem for p in INPUTS])
def test_fixture(path: Path) -> None:
    expected = expected_output(path)
    if expected.suffix == ".error":
        with pytest.raises(ScoreError) as caught:
            solfege_colinha(path)
        assert caught.value.message == read_text(expected).rstrip("\n")
    else:
        assert solfege_colinha(path) + "\n" == read_text(expected)


def test_second_part_is_read_defect_2() -> None:
    parts = parse_score(FIXTURES / "input" / "two_parts.xml")
    assert [p.name for p in parts] == ["Trombone", "Tuba"]
    assert solfege_colinha(FIXTURES / "input" / "two_parts.xml", part_index=1) == "sol Lá"


def test_messages_name_the_users_file_not_the_temp_file() -> None:
    with pytest.raises(ScoreError, match=r"“Canção\.xml” doesn't contain a score"):
        parse_score(FIXTURES / "input" / "not_xml.xml", "Canção.xml")


def test_mxl_container(tmp_path: Path) -> None:
    mxl = tmp_path / "accidentals.mxl"
    with zipfile.ZipFile(mxl, "w") as archive:
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container><rootfiles>'
            '<rootfile full-path="score.xml" media-type="application/vnd.recordare.musicxml+xml"/>'
            "</rootfiles></container>",
        )
        archive.write(FIXTURES / "input" / "accidentals.xml", "score.xml")
    assert solfege_colinha(mxl) + "\n" == read_text(FIXTURES / "output" / "accidentals.txt")


@pytest.mark.parametrize(
    ("content", "message"),
    [
        pytest.param(b"PK\x03\x04 truncated", "seems to be damaged", id="truncated-zip"),
        pytest.param(bytes(range(256)) * 4, "doesn't contain a score", id="random-bytes"),
    ],
)
def test_broken_mxl(tmp_path: Path, content: bytes, message: str) -> None:
    mxl = tmp_path / "song.mxl"
    mxl.write_bytes(content)
    with pytest.raises(ScoreError, match=message):
        parse_score(mxl)


def test_score_with_no_parts_is_not_a_score(tmp_path: Path) -> None:
    path = tmp_path / "empty_score.xml"
    path.write_text(
        '<?xml version="1.0"?><score-partwise version="4.0"><part-list/></score-partwise>',
        encoding="utf-8",
    )
    with pytest.raises(ScoreError, match="doesn't contain a score"):
        parse_score(path)


def test_chord_takes_lowest_note_and_percussion_is_skipped(tmp_path: Path) -> None:
    path = tmp_path / "chord.xml"
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <part-list><score-part id="P1"><part-name>Test</part-name></score-part></part-list>
  <part id="P1"><measure number="1">
    <note><pitch><step>E</step><octave>3</octave></pitch><duration>1</duration></note>
    <note><chord/><pitch><step>C</step><octave>3</octave></pitch><duration>1</duration></note>
    <note><unpitched><display-step>C</display-step><display-octave>5</display-octave></unpitched>
      <duration>1</duration></note>
    <note><pitch><step>G</step><octave>3</octave></pitch><duration>1</duration></note>
  </measure></part>
</score-partwise>""",
        encoding="utf-8",
    )
    assert solfege_colinha(path) == "dó sol"


def test_detect_base_octave_without_notes_has_a_default() -> None:
    assert detect_base_octave([]) == 4
