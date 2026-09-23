# notation_service — implementation plan

## Context

Musicians in this project read from a cheat sheet called a **colinha**: a bare list of note names,
one line per measure, with no staff and no rhythm. Producing one from a score is currently a
manual job — open a notebook, edit a hardcoded file path, run a cell, copy the output.

This project turns that conversion into a small local web app. You drop a MusicXML file on a page
and get the colinha back, in either of two notations. It installs with one installer, launches
from a desktop icon that starts the server, opens the browser, and shuts itself down once you stop
using it. No Docker, no terminal, no daemon left running.

**The product runs on Windows.** It is developed on Linux, so Windows compatibility is designed in
from the first step and checked continuously, not ported at the end.

**The users are musicians, not programmers.** They export a file from MuseScore and want a
colinha. They will not open a terminal, read a log, or know what MusicXML is. Their mistakes —
the wrong file, a damaged file, a file with no notes — are the normal case, and each one gets a
clear message that tells them what to do next.

The conversion logic originates in a Jupyter notebook that is **not** part of this project and is
not available to it. Everything that logic knew is written down below, so this directory is
self-contained: nothing here reads from, imports from, or needs to be diffed against anything
outside it.

### Requirements fixed with the user

- **Runs on Windows.** Installed and used on Windows by non-technical users; developed and
  unit-tested on Linux.
- **User-friendly first.** One installer, one icon, one button. No required choices; defaults are
  right for the common case.
- **Every human error has a plain-language message and a test.** See *Error catalogue*.
- **Clean, idiomatic Python** — typed, linted, small functions, tested first. See *Code quality*.
- **Input is MusicXML only** — `.xml`, `.musicxml`, `.mxl`. No PDF ingestion, no external
  conversion service, no polling, no job queue.
- **Both notations are offered**, selected on the form.
- **`music21` does the parsing.** Existing packages are strongly preferred over new code.
- **Launch is idempotent with idle auto-shutdown.** Clicking the icon twice must not start two
  servers; leaving it alone must not leave a process behind.
- **Rests are dropped and whitespace collapsed** — see *Rest handling* below.

### Open decisions

Work went ahead on the proposals; each still needs the user's confirmation:

| # | Question | Proposal | Status |
| --- | --- | --- | --- |
| D1 | How do Windows users install it? | PyInstaller one-folder build wrapped in an Inno Setup installer — the user needs no Python. Alternative: user installs Python, runs a PowerShell script. | Implemented as proposed. |
| D2 | Language of the page and messages | Portuguese, matching the users. Drafts below are English until confirmed. | **Open** — the page and messages are still English. |
| D3 | `tests/fixtures/output/` holds notebook-era output (ragged spaces, `NameError`) | Regenerate to the agreed behaviour; keep the old output only where it documents a fixed defect. | Regenerated; `no_rehearsal_mark.error` became a `.txt`. |
| D4 | `eletro_farra_trombone.xml` is a real score, against the fixture rule | Keep as the single real-world regression fixture, or remove it. | Kept. |

## The notation

### Solfège dialect

Each note becomes its Portuguese solfège name:

| step | C | D | E | F | G | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| name | dó | ré | mi | fá | sol | lá | sí |

Octave is encoded as **letter casing**, relative to the score's base octave (see below):

| octave | rendering | example |
| --- | --- | --- |
| base and below | lowercase | `sí♭` |
| base + 1 | Title case | `Sí♭` |
| base + 2 and above | UPPERCASE | `SÍ♭` |

Accidentals are appended from the note's `alter` value: `-1` → `♭`, `+1` → `#`, `0` → nothing.

Measures are rendered one per line, notes separated by single spaces. A section beginning at a
rehearsal mark is titled with that mark.

Worked example, base octave 2:

```
Love story
fá Fá Fá
Lá♭ Lá♭ Sí♭
Ré♭ Mi♭ Fá
```

### Letters dialect

The same score in plain letter names with octave shown as an arrow rather than casing — base
octave is bare, one above is `↑`, one below is `↓` — and measures joined by ` | `:

```
Ab G | F | Bb↑ Eb | F
```

### Base octave

Both dialects need a reference octave. It is **detected from the score**: the octave of the lowest
sounding note across the whole file. The form offers an override for scores where the automatic
choice reads badly.

This matters because the original notebook hardcoded the tiers as `octave 2 → lower, 3 → Title,
4+ → UPPER`. Those numbers are correct for bass-clef trombone and tuba and wrong for every other
instrument. Detection reproduces the hardcoded behaviour exactly for a bass-clef part — whose
lowest note is octave 2 — while also working for the rest.

### Rest handling

Rests are **dropped**, and each line is then collapsed to single spaces with no leading or
trailing padding. A measure containing only rests renders as a blank line.

This is a deliberate change from the original notebook, which emitted an empty string per rest and
left the spaces in. On a real score — the one this was checked against had 161 rests — that
produced ragged output like `Fá   Fá  Sol ` where the gaps carried no information a reader could
use.

## Defects being fixed, not reproduced

The originating notebook had three bugs. They are recorded here because the fixes need tests, and
because someone comparing this app's output against an old colinha will notice the differences.

1. **Sharps never rendered.** The accidental check compared `alter` against the string `"+1"`,
   but MusicXML emits `"1"`. Every sharp silently came out as a natural.
2. **Only the first part was read.** A multi-part score had everything after part one ignored.
   Here, the part is selectable and defaults to the first.
3. **A score with no rehearsal marks crashed.** The section variable was only assigned inside the
   "found a rehearsal mark" branch, so a file without one raised `NameError` on the first measure.
   Here, measures before any rehearsal mark form an untitled leading section.

A fourth difference was found when checking against the real score: where the same rehearsal
mark appears twice (`eletro_farra_trombone.xml` repeats *Heads will roll* and *Blinding lights*
two measures apart), the notebook kept only the second, silently dropping the measures between
them. Here every measure is kept and the heading appears twice, as it does in the score.

## User experience

The whole visible surface is designed for a musician who has never heard of MusicXML.

- **Zero required choices.** Choose a file, press *Convert*, get a correct colinha. Dialect,
  base octave, and instrument (part) default sensibly and sit below the main button.
- **Instruments by name.** The part selector lists the instrument names from the file ("Trombone",
  "Tuba"), not "part index 1". If the file has one instrument, the selector is hidden.
- **Plain words.** No "parse error", "413", "part index", or exception names anywhere visible.
- **Every message answers three questions:** what went wrong in the user's terms, which file (by
  name), and what to do next.
- **Nothing is lost on failure.** A failed conversion re-renders the form with the user's choices
  still selected, and the message beside the file field.
- **The result is easy to take away.** A *Copy* button and a *Download .txt* button, and the
  colinha in a large, readable monospace block.
- **Nothing to manage.** No console window, no process to stop, no files left behind. A second
  click opens a new tab; walking away shuts it down.
- **The launcher never fails silently.** Where there is no page to show a message on, a native
  Windows dialog (`tkinter.messagebox`) shows it.

## Error catalogue

Wrong input is the normal case. **This table is the single source of truth** for the mistakes the
app handles and what it says about each; `CLAUDE.md`, the tests, and *Verification* refer to rows
by ID and never copy them. IDs are permanent — a retired entry keeps its number, and a new one
takes the next free ID.

Each entry has one test, in a parametrized `test_error_catalogue` per layer, with the ID as the
case id (`pytest.param(..., id="E02")`). The test asserts the message text, that the response is a
rendered page (never a traceback), and that the form choices survived. A wording change is made
here and in the test together. Message wording is a draft pending D2. File names shown in
*italics* here appear on the page in “curly quotes”, since messages are plain text.

| ID | Mistake | Where caught | Message (draft) |
| --- | --- | --- | --- |
| E01 | Convert pressed with no file | `views` | "Choose a score file first — the one you exported from MuseScore." |
| E02 | MuseScore project file (`.mscz`, `.mscx`) | `views` | "*song.mscz* is a MuseScore project. In MuseScore use *File → Export → MusicXML*, then upload the exported file." |
| E03 | Other wrong type (PDF, image, `.mid`, `.docx`) | `views` | "*song.pdf* isn't a score file this app can read. Export the score from MuseScore as MusicXML (`.musicxml`, `.xml` or `.mxl`)." |
| E04 | Empty (0-byte) file | `views` | "*song.xml* is empty. Try exporting it again." |
| E05 | File over the size limit | `views` | "*song.xml* is larger than 10 MB, which is more than any single score should be. Check that it is the right file." |
| E06 | Not XML at all (renamed `.txt`) | `parsing` | "*song.xml* doesn't contain a score. Check it is the file exported from MuseScore." |
| E07 | Truncated or corrupt XML; `.mxl` that isn't a zip | `parsing` | "*song.xml* seems to be damaged. Try exporting it from MuseScore again." |
| E08 | Well-formed XML that isn't a score | `parsing` | Same as E06. |
| E09 | Score with no pitched notes (only rests, only percussion) | `parsing` | "*song.xml* has no notes to write out for *Drums*. Choose another instrument or file." |
| E10 | Instrument beyond those in the file (tampered form) | `views` | "This file has 2 instruments; choose one from the list." |
| E11 | Base octave override out of range (0–8) | `views` | "Base octave must be between 0 and 8." |
| E12 | Filename with accents, spaces, or non-Latin characters | — | Not an error: must convert, and display the name correctly. |
| E13 | Launcher: port taken by another program | `launcher` | Dialog: "Another program is using port 5117. Close it, or restart the computer, and try again." |
| E14 | Launcher: server didn't start within 15 s | `launcher` | Dialog: "The converter didn't start. Details were saved to *<full log path>*." |
| E15 | Any unexpected exception | top-level handler | "Something went wrong converting *song.xml*. It has been logged." — traceback to the log only. |

`ScoreError` carries the user-facing message, written in `parsing.py` where the failure is
understood. `views.py` renders it; it never builds a message from a third-party exception's text.

When a real user hits a mistake not in this table, add a row and a failing test before the fix.

## Code quality

- **Python 3.12+**, `src/` layout, all metadata and tool configuration in `pyproject.toml`.
- **`ruff`** (lint + format) and **`mypy --strict`** run clean; **`pytest-cov`** with a coverage
  floor of 90 % on the pure core.
- Type-annotated signatures; frozen dataclasses across module boundaries; `Enum` for closed sets.
- Small functions named with the domain vocabulary; comments explain *why*, not *what*.
- No bare `except`; one top-level handler (E15) is the only `except Exception`.
- `logging` in the shell, never `print`; the pure core does not log.
- No import-time side effects; the app is built in `create_app()`.
- Bugs are fixed test-first.

## Windows portability rules

- `pathlib.Path` everywhere; per-user locations from `platformdirs`.
- `encoding="utf-8"` on every text open; the download is `text/plain; charset=utf-8`.
- Upload temp file created with `delete=False`, closed before parsing, unlinked in `finally` —
  an open `NamedTemporaryFile` cannot be reopened by name on Windows.
- No `SIGTERM` for shutdown (it is `TerminateProcess` on Windows). No `start_new_session` without
  the Windows `creationflags` counterpart. Platform branches live in one function each, in the
  shell, and are tested.
- The icon's entry point is a `[project.gui-scripts]` script, so no console window appears.

## Infrastructure decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Parsing | `music21` | Handles `.mxl` zip containers, tie resolution, `alter` → accidental, octave numbering, and multi-part scores. Hand-writing that plumbing is exactly what produced defects 1–3 above. |
| Statefulness | None | The upload is parsed from a temp file and deleted in a `finally`. No database, no session, no uploads directory, no queue. Nothing to corrupt and nothing to clean up. The log file is the only thing written. |
| WSGI server | `waitress` | Pure Python, no C build step, runs identically on Windows and Linux. Flask's development server is explicitly not for this. |
| Frontend | Jinja2 + vendored classless Pico.css | Server-rendered; the form works with JavaScript disabled. The stylesheet is committed to `static/`, never fetched from a CDN, so the app works offline. |
| Lifetime | Idle watchdog → `server.close()` on waitress | About twenty lines of `threading`. Uses waitress's own API instead of a signal, because signals are POSIX-only in any graceful sense. |
| Per-user paths | `platformdirs` | Correct log location on Windows (`%LOCALAPPDATA%`) and Linux without hand-written branches. |
| Launcher errors | `tkinter.messagebox` | Ships with Python and bundles with PyInstaller; a native dialog instead of a vanishing console. |
| Port | `5117`, `NOTATION_PORT` overrides | Uncommon enough to avoid collisions; a fixed default keeps the launcher's health check trivial. |
| Packaging (D1) | PyInstaller one-folder + Inno Setup | The user needs no Python. One-folder avoids the antivirus false positives common with one-file builds. Inno Setup gives a Start menu entry, a desktop icon, and an entry in *Apps & features* for uninstalling. Builds must run on Windows, so they run in CI. |
| CI | GitHub Actions, `ubuntu-latest` + `windows-latest` | The only practical way to run the suite on real Windows on every push from a Linux machine. |
| Binding | `127.0.0.1` only | This is a personal tool. It has no authentication and should not be reachable from the network. Also avoids a Windows Firewall prompt. |

Known limitation: the build is unsigned, so Windows SmartScreen will show *"Windows protected your
PC"* on first install. The README shows the user *More info → Run anyway* with a screenshot. Code
signing is out of scope unless the user asks for it.

## Layout

```
notation_service/
├── CLAUDE.md                      # conventions for future work in this directory
├── PLAN.md                        # this document
├── README.md                      # for users: install, use, uninstall — with screenshots
├── pyproject.toml                 # dependencies, console/gui scripts, ruff/mypy/pytest config
├── .github/workflows/ci.yml       # lint + types + tests on Linux and Windows; Windows build
├── scripts/check.sh               # runs every local automated check, prints a summary
├── packaging/
│   ├── notation_service.spec      # PyInstaller
│   └── installer.iss              # Inno Setup
├── assets/{icon.svg,icon.ico}
├── src/notation_service/
│   ├── __init__.py                # create_app() factory
│   ├── config.py                  # Config dataclass, environment-driven
│   ├── model.py                   # Note / Measure / Song — no music21, no Flask
│   ├── parsing.py                 # music21 → model; ScoreError with user-facing messages
│   ├── dialects.py                # model → text
│   ├── views.py                   # Flask blueprint
│   ├── idle.py                    # idle-shutdown watchdog
│   ├── server.py                  # waitress entrypoint
│   ├── launcher.py                # start-or-attach, open the browser, dialogs on failure
│   ├── templates/{base,index}.html
│   └── static/{pico.min.css,app.css}
└── tests/
    ├── conftest.py
    ├── fixtures/{input,output}/   # hand-authored scores and expected colinhas
    ├── test_dialects.py
    ├── test_parsing.py
    ├── test_views.py              # includes the parametrized error catalogue E01–E12, E15
    ├── test_idle.py
    └── test_launcher.py           # E13, E14, start-or-attach, platform spawn branch
```

The structural rule is a **pure core** (`model.py`, `dialects.py`, and the transformation half of
`parsing.py`) with no Flask, no paths, and no I/O, wrapped in a thin **imperative shell**
(`views.py`, `server.py`, `launcher.py`, `idle.py`, `config.py`). Everything worth testing is
therefore testable without a request context.

## Implementation steps

Each step ends at a checkpoint. A step is finished when its checkpoint passes **on both Linux and
Windows CI**, not just locally.

### Step 0 — Tooling and CI first

`pyproject.toml` with runtime dependencies `flask`, `music21`, `waitress`, `platformdirs`; dev
extras `pytest`, `pytest-cov`, `ruff`, `mypy`. Tool configuration in the same file.

`scripts/check.sh` runs, in order, `ruff check`, `ruff format --check`, `mypy --strict src`,
`pytest --cov`, then the suite again under `PYTHONUTF8=0 LC_ALL=C`, and prints one PASS/FAIL line
per check.

`.github/workflows/ci.yml` runs the same checks on `ubuntu-latest` and `windows-latest`.

**Checkpoint:** an empty test suite passes `scripts/check.sh` locally and both CI jobs are green.
From here on, Windows breakage shows up on the push that causes it.

### Step 1 — The pure core

`model.py` — frozen dataclasses, nothing else:

```python
@dataclass(frozen=True)
class Note:
    step: str        # "C".."B"
    octave: int
    alter: int       # -1, 0, or 1

@dataclass(frozen=True)
class Measure:
    notes: tuple[Note, ...]

@dataclass(frozen=True)
class Song:
    title: str | None    # the rehearsal mark, or None for a leading section
    measures: tuple[Measure, ...]
```

`dialects.py` — two renderers with the same signature,
`(song: Song, base_octave: int) -> str`, registered in a `DIALECTS` mapping of key → (label,
function). `views.py` and the template both read that mapping, so adding a dialect touches only
this file and its tests.

Implement `render_solfege` and `render_letters` per *The notation* above. Both collapse each
measure to single-space-separated tokens, so rest-dropping needs no special casing downstream.

**Checkpoint:** `pytest tests/test_dialects.py`. Table-driven cases covering: flat, sharp (this is
where defect 1 is pinned), natural, each of the three casing tiers, a note below the base octave,
an all-rest measure, and an empty song.

### Step 2 — Parsing, and the example scores

Fixtures are hand-authored minimal MusicXML pairs, `input/<name>.xml` with `output/<name>.txt`
(or `.error` for expected failures) — accidentals, octave casing, multiple sections, no rehearsal
mark, ties and rests. Add inputs for the parsing-layer errors: not XML (E06), truncated XML (E07),
XML that isn't a score (E08), a score with only rests (E09), and a two-part score for part
selection and defect 2. Resolve D3 and D4 before this step's checkpoint.

`parsing.py` exposes:

```python
def parse_score(path: Path, part_index: int = 0) -> list[Song]: ...
def list_parts(path: Path) -> list[str]: ...        # instrument names, for the selector
def detect_base_octave(songs: Sequence[Song]) -> int: ...
```

- `converter.parse(path)` handles `.xml`, `.musicxml`, and `.mxl` transparently.
- Iterate the chosen part's measures.
- Take pitched notes only; music21 excludes rests from `measure.notes`, which is what implements
  the agreed rest-dropping.
- **Skip a note tied *into*** — `n.tie is not None and n.tie.type in {"stop", "continue"}`. A note
  held across a barline is struck once and should appear once.
- Read `n.pitch.step`, `n.pitch.octave`, `int(n.pitch.alter)`.
- For a chord, take the lowest pitch and note the choice in a comment; the parts this is used for
  are single-line.
- A rehearsal mark starts a new `Song` titled with it. *Verified:* music21 surfaces
  `RehearsalMark` inside the measure for a real MuseScore export (`eletro_farra_trombone.xml`),
  so no `ElementTree` fallback is needed.
- *Verified:* music21 reads ties from `<tie>` (sound), not `<tied>` (notation). MuseScore writes
  both; hand-authored fixtures must too.
- Wrap every music21 failure in a single `ScoreError` whose message is the user-facing text from
  the error catalogue, distinguishing E06/E07/E08/E09. The original exception is chained
  (`raise ... from exc`) so the log keeps it.

**Checkpoint:** `pytest tests/test_parsing.py` against every fixture, asserting the rendered
solfège text end to end, and the exact message for each error fixture.

### Step 3 — The Flask application

`config.py` — a `Config` dataclass built from the environment: `NOTATION_PORT` (5117),
`NOTATION_IDLE_MINUTES` (20), `NOTATION_MAX_UPLOAD_MB` (10), allowed suffixes
`.xml .musicxml .mxl`. Invalid environment values fall back to the default and log a warning;
they never stop the app from starting.

`__init__.py` — `create_app(config: Config | None = None)` registering the blueprint, which holds
the top-level handler (E15). E05 is checked in `views` on the saved upload rather than by a `413`
handler: a `413` is raised before the form is parsed, so it could neither name the file nor keep
the user's choices.

`views.py`:

- `GET /` — the form: file input, *Convert* button, and below it the dialect radio built from
  `DIALECTS`, the base-octave select defaulting to "automatic", and the instrument selector.
- `POST /` — write the upload to a temp file per *Windows portability rules*, parse, render, and
  unlink in a `finally`. Re-render the same page with the result. No redirect, no session, no
  stored file.
- *Download .txt* is a `data:text/plain;charset=utf-8` link beside the result, named after the
  uploaded file (`song.xml` → `song - colinha.txt`). It replaces the planned `POST` with
  `download=1`: after a conversion the file field is empty, so a second `POST` would make the user
  choose the file again. The link needs no JavaScript and no server state.
- `GET /healthz` — `{"status": "ok", "app": "notation_service"}`, excluded from the idle timer.
  The `app` field lets the launcher tell this server from another program on the same port (E13).

Templates: `base.html` links the vendored `pico.min.css` and `app.css`; `index.html` is the form,
an error area next to the file field, a `<pre>` result, and a copy-to-clipboard button in vanilla
JavaScript added as progressive enhancement.

**Checkpoint:** `pytest tests/test_views.py` — happy path in both dialects, the download, and one
parametrized test covering E01–E12 and E15, each asserting message, status, no traceback, and
preserved form choices. Then run it and walk through V3 and V4 below by hand.

### Step 4 — Idle shutdown and the server entrypoint

`idle.py` — `IdleWatchdog(timeout_seconds, on_idle)`, a daemon `threading.Timer` reset from a
`before_request` hook that skips `/healthz` and `/static/`. `on_idle` is injected, so the test
passes a stub and the server passes the waitress server's `close`.

`server.py` — build the config and the app, set up a rotating log file under
`platformdirs.user_log_dir("notation_service")`, create the server with
`waitress.create_server` bound to `127.0.0.1`, start the watchdog, and `run()`.

*Verified on Linux:* `server.close()` from the watchdog thread ends `run()`, and a request still in
flight completes first. `test_real_spawn_attach_and_idle_exit` checks the same on Windows CI.

**Checkpoint:** `pytest tests/test_idle.py` with a stubbed `on_idle`, then run the server with
`NOTATION_IDLE_MINUTES=0.25` and confirm it exits on its own, and that a request resets the clock.

### Step 5 — Launcher

`launcher.py`, standard library only — `urllib`, `subprocess`, `webbrowser`, `time`, `tkinter`:

1. `GET /healthz` with a short timeout. Our server answering → open the browser and exit 0.
   Something else answering on the port → E13 dialog, exit non-zero.
2. Otherwise spawn the server detached with no console window — one function holding the
   platform branch (`creationflags` on Windows, `start_new_session` elsewhere).
3. Poll `/healthz` for up to 15 seconds.
4. Healthy → open the browser. Timed out → E14 dialog with the full log path, exit non-zero.

A fast double-click can start two launchers that both spawn a server. That is safe: the second
server fails to bind and exits, and both launchers find the first one healthy.

Scripts: `notation-service` (gui-script) → `launcher:main`, `notation-service-server` →
`server:main`.

**Checkpoint:** `pytest tests/test_launcher.py` — attach to a running server, spawn when none,
E13 with a stub server on the port, E14 with a server that never answers; dialogs stubbed.

### Step 6 — Windows packaging

`packaging/notation_service.spec` builds a one-folder PyInstaller bundle including music21's data,
the templates, static files, and the `.ico`. `packaging/installer.iss` wraps it: per-user install
(no administrator rights), Start menu entry, optional desktop icon, uninstaller registered in
*Apps & features*. Re-running the installer over an existing install upgrades it in place.

The Windows CI job builds the installer and uploads it as a workflow artifact — that `.exe` is
what gets tested in the VM (V5).

**Checkpoint:** CI produces `notation_service-setup.exe`, and V5 passes on it.

### Step 7 — Documentation

`README.md` for users: download, install (including the SmartScreen step, with a screenshot),
use, uninstall, and where the log is. A short *Development* section at the end for the developer.

Revisit `CLAUDE.md` and correct anything the implementation disproved — in particular the
rehearsal-mark question from Step 2 and the `server.close()` question from Step 4.

## Verification

This is the developer's checklist. Every check has an ID, the exact action, and what "pass" looks
like. Copy the relevant sections into the pull request or release notes and tick them; a release
is not handed to users until V1–V6 are all ticked for that build.

### V1 — Automated checks, locally (every change)

| ID | Run | Pass looks like |
| --- | --- | --- |
| V1.1 | `scripts/check.sh` | Every line `PASS`; exit code 0. |
| V1.2 | `.venv/bin/ruff check . && .venv/bin/ruff format --check .` | No findings, no files to reformat. |
| V1.3 | `.venv/bin/mypy --strict src` | `Success: no issues found`. |
| V1.4 | `.venv/bin/pytest --cov=notation_service --cov-report=term-missing` | All green; core modules ≥ 90 %; review the *Missing* column for untested branches. |
| V1.5 | `PYTHONUTF8=0 LC_ALL=C .venv/bin/pytest` | All green — nothing relies on the default encoding. |
| V1.6 | `.venv/bin/pytest -k test_error_catalogue -v` | Exactly one passing case per catalogue ID (E01–E15 today), each shown as `[E0n]`; none skipped, none missing. |

### V2 — Windows CI (every push)

| ID | Check | Pass looks like |
| --- | --- | --- |
| V2.1 | Both matrix jobs of the latest run | Green on `ubuntu-latest` and `windows-latest`. |
| V2.2 | Test count in each job's log | Identical, or every difference is an explicit platform skip with a reason. |
| V2.3 | Windows build artifact | `notation_service-setup.exe` attached to the run. |

### V3 — Conversions by hand (Linux, before merging a change to parsing or dialects)

Start with `.venv/bin/python -m notation_service.server` and open `http://127.0.0.1:5117`.

| ID | Action | Pass looks like |
| --- | --- | --- |
| V3.1 | Convert each `tests/fixtures/input/*.xml` in solfège | Output matches the corresponding `output/*.txt` exactly. |
| V3.2 | `accidentals.xml` in solfège | The sharp renders as `#`, not as a natural (defect 1). |
| V3.3 | Two-part fixture, choose the second instrument | Its notes, not the first part's (defect 2). Selector shows instrument names. |
| V3.4 | `no_rehearsal_mark.xml` | Converts; untitled leading section; no error (defect 3). |
| V3.5 | `multiple_sections.xml` | Each rehearsal mark is a heading; measures before the first form an untitled section. |
| V3.6 | `ties_and_rests.xml` | No double spaces, no leading or trailing spaces; tied note appears once; all-rest measure is a blank line. |
| V3.7 | Any fixture in letters | ` \| ` separators; `↑` / `↓` arrows relative to the base octave. |
| V3.8 | Override base octave up and down by one | Casing / arrows shift accordingly; automatic value restored when set back. |
| V3.9 | *Download .txt* | File named `<name> - colinha.txt`, byte-identical to the screen text, opens correctly as UTF-8. |
| V3.10 | *Copy*, paste into a text editor | Identical to the screen, accents and `♭` intact. |
| V3.11 | Disable JavaScript and convert | Form still works; only the copy button is absent. |
| V3.12 | Disconnect the network and reload | Page is fully styled — nothing loads from a CDN. |

### V4 — Human-error walkthrough (Linux, before merging any change to views, parsing, or launcher)

Create the bad inputs in the scratch directory:

```sh
: > empty.xml                                        # E04
echo "shopping list" > notes.txt && cp notes.txt fake.xml   # E03 / E06
head -c 400 tests/fixtures/input/accidentals.xml > truncated.xml   # E07
echo '<?xml version="1.0"?><recipe/>' > recipe.xml  # E08
truncate -s 11M big.xml                              # E05
cp tests/fixtures/input/accidentals.xml "Canção de São João.xml"   # E12
cp tests/fixtures/input/accidentals.xml "song.mscz"  # E02 (name only is enough)
```

For each row: the message is visible next to the file field, names the file, says what to do,
contains no technical terms, and the dialect/octave/instrument choices you set beforehand are
still selected.

| ID | Action | Pass looks like |
| --- | --- | --- |
| V4.1 | Press *Convert* with no file | E01 message. |
| V4.2 | Upload `song.mscz` | E02 — explains *File → Export → MusicXML*. |
| V4.3 | Upload `notes.txt`, then any PDF or image | E03 for both, naming the file. |
| V4.4 | Upload `empty.xml` | E04. |
| V4.5 | Upload `big.xml` | E05 stating the limit; no "413" or "Request Entity Too Large" anywhere. |
| V4.6 | Upload `fake.xml` | E06. |
| V4.7 | Upload `truncated.xml` | E07. |
| V4.8 | Upload `recipe.xml` | E08. |
| V4.9 | Upload the all-rests fixture | E09. |
| V4.10 | Edit the instrument field in dev tools to `99`, submit | E10 with the real instrument count. |
| V4.11 | Edit the octave field to `42`, submit | E11. |
| V4.12 | Upload `Canção de São João.xml` | Converts; name displayed and used in the download filename correctly. |
| V4.13 | Temporarily raise an exception in `render_solfege`, convert | E15 on the page; full traceback in the log; nothing technical in the browser. Revert. |
| V4.14 | After all of the above, list the system temp directory | No leftover upload files. |

### V5 — End to end on Windows (before every release, in a VM)

Set up once on the Linux host: `quickget windows 11 && quickemu --vm windows-11.conf`. Download the
`notation_service-setup.exe` artifact from the CI run (V2.3) into the VM. Use a **standard,
non-administrator** Windows account, ideally one whose username contains an accent (e.g.
`João`), since that puts non-ASCII characters in every per-user path.

| ID | Action | Pass looks like |
| --- | --- | --- |
| V5.1 | Run the installer | SmartScreen warning as documented in the README; install completes without an admin prompt. |
| V5.2 | Look for the app | *Notation Converter* in the Start menu, and on the desktop if chosen. Icon renders. |
| V5.3 | Click the icon | Default browser (Edge) opens on the page within a few seconds. **No console window appears at any point.** No Windows Firewall prompt. |
| V5.4 | Repeat V3.1–V3.7 with files copied into the VM | Same results as on Linux. |
| V5.5 | Repeat V4.1–V4.12 | Same messages as on Linux. |
| V5.6 | Convert a file from *Documents* (OneDrive-synced if available) and from the desktop | Both work. |
| V5.7 | *Download .txt*, open it in Notepad | Accents, `♭`, `↑` display correctly. |
| V5.8 | Click the icon again while it's running | A new tab opens; Task Manager shows **one** server process. |
| V5.9 | Double-click the icon very fast, twice | Still one server process after a few seconds; both tabs work. |
| V5.10 | Start another program on port 5117 (`python -m http.server 5117`), click the icon | E13 dialog, readable, naming the port. |
| V5.11 | Leave it idle past `NOTATION_IDLE_MINUTES` (set it to 1 for the test via a user environment variable) | Server process gone from Task Manager; clicking the icon starts it again normally. |
| V5.12 | Open `%LOCALAPPDATA%\notation_service\Logs\` | `server.log` exists and contains the E15 traceback from V4.13 if repeated here; nothing else was written anywhere. |
| V5.13 | Disconnect the VM's network, click the icon | Works fully offline and is styled. |
| V5.14 | Run the installer again over the existing install | Upgrades in place; icon still works; no duplicate shortcuts. |
| V5.15 | Uninstall from *Settings → Apps* | Shortcuts and program folder gone; no process left running. |

### V6 — Release sign-off

- [ ] V1 all green on the release commit.
- [ ] V2 green on both platforms for the same commit; the tested installer came from that run.
- [ ] V3 and V4 ticked since the last change to parsing, dialects, views, or launcher.
- [ ] V5 fully ticked in a fresh VM snapshot on this exact installer.
- [ ] README screenshots match the current UI.
- [ ] Any new user mistake found during testing has a catalogue row and a test.
