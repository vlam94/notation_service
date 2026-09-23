# notation_service

A local-only Flask app that converts a MusicXML file into **colinha** notation. It installs with
one step, launches from a desktop icon that opens the browser for you, and shuts itself down once
you stop using it.

**The product runs on Windows.** Development happens on Linux, but a feature is not done until it
works on Windows — see *Windows is the target platform*, below. The people using this are
musicians, not programmers: they will never open a terminal, read a log, or know what MusicXML
is. Design every visible surface for them.

This directory is self-contained. It does not read from, import from, or need to be compared
against anything outside itself. `PLAN.md` is the agreed design and the source of truth for scope;
read it before making structural changes.

## Domain vocabulary

Use these words in code and in conversation — they are the project's terms, not generic ones.

- **colinha** — the cheat sheet this app produces: note names only, one line per measure, no staff
  and no rhythm. The Portuguese word is kept deliberately; it is what the people using this call
  it.
- **dialect** — a way of rendering a parsed score as text. Two exist: *solfège* and *letters*.
- **base octave** — the reference octave a rendering is relative to. Detected as the octave of the
  lowest sounding note in the score, and overridable from the form.
- **section** — a run of measures beginning at a rehearsal mark, rendered under its own heading.
  One file often holds several. Modelled as `Song`.

## The notation

Note names in the **solfège** dialect:

| step | C | D | E | F | G | A | B |
| --- | --- | --- | --- | --- | --- | --- | --- |
| name | dó | ré | mi | fá | sol | lá | sí |

Octave is carried by **letter casing**, relative to the base octave: at or below it, lowercase
(`sí♭`); one above, Title case (`Sí♭`); two or more above, UPPERCASE (`SÍ♭`). Accidentals append
to the name — `alter` of `-1` gives `♭`, `+1` gives `#`, `0` gives nothing. Measures are one per
line, notes single-space separated.

The **letters** dialect renders the same score as plain letter names with octave as an arrow
instead of casing — base octave bare, one above `↑`, one below `↓` — and joins measures with
` | `:

```
Ab G | F | Bb↑ Eb | F
```

**Rests are dropped** and each line is collapsed to single spaces with no leading or trailing
padding; a measure of nothing but rests renders as a blank line. This is a deliberate decision,
not an oversight — see `PLAN.md` for why.

**Notes tied into are skipped.** A note held across a barline is struck once, so it appears once.
Only the tie's starting note is rendered.

## Architecture: pure core, imperative shell

This split is the main structural rule. Keep it.

**Pure core** — `model.py`, `dialects.py`, and the transformation half of `parsing.py`. No Flask,
no `request`, no filesystem paths, no `print`, no environment reads. Functions take data and
return data. Everything worth testing lives here and is tested without a request context.

**Imperative shell** — `views.py`, `server.py`, `launcher.py`, `idle.py`, `config.py`. These own
I/O, HTTP, and process lifetime, and should stay thin enough that a bug is unlikely to hide in
them.

Concretely: if you are tempted to import `flask` into `dialects.py`, or to pass a `FileStorage`
into `parse_score`, the boundary is being crossed and the design needs a different shape instead.

`parsing.py` is the one module that touches both worlds. It takes a `Path` and returns model
objects, and it converts every music21 failure into a single `ScoreError` — so no other module
ever imports music21 just to catch an exception.

## Prefer an existing package over new code

This is an explicit constraint from the user, and it is stronger than the usual preference. Before
writing a helper, check whether a well-maintained package already does the job, and use that.

The parsing layer exists *because* of this rule. `music21` already handles `.mxl` zip containers,
tie resolution, `alter` → accidental, octave numbering, and multi-part scores. The hand-rolled
version this app replaces got three of those cases wrong (see *Known defects*, below).

Two acknowledged exceptions, both small and both deliberate:

- `idle.py` — an idle-shutdown watchdog. No package covers this cleanly for a WSGI app, and it is
  roughly twenty lines of `threading`. It stops waitress through waitress's own API, not with
  `SIGTERM` — on Windows `os.kill(pid, SIGTERM)` is `TerminateProcess`, a hard kill.
- the dialect renderers — they encode this project's own notation, so by definition nothing
  external implements them.

A third exception needs justifying here.

## Known defects in the prior implementation

The conversion logic came from a Jupyter notebook that is not part of this project. It carried
three bugs. They are fixed here, each pinned by a test, and recorded because anyone comparing this
app's output against an older colinha will notice the differences:

1. **Sharps never rendered** — the accidental check compared `alter` against `"+1"` while
   MusicXML emits `"1"`, so every sharp came out as a natural.
2. **Only the first part was read** in a multi-part score. The part is now selectable.
3. **A score with no rehearsal marks crashed** with `NameError`, because the section variable was
   only assigned inside the branch that found a mark. Measures before the first mark now form an
   untitled leading section.

A fourth difference: where the same rehearsal mark appears twice, the notebook kept only the
second and dropped the measures between them. This app keeps every measure and repeats the heading.

It also hardcoded the casing tiers to `octave 2 → lower, 3 → Title, 4+ → UPPER`. Those numbers are
right for bass-clef trombone and tuba and wrong for everything else, which is why the base octave
is detected instead.

## Adding a dialect

1. Write `render_<name>(song: Song, base_octave: int) -> str` in `dialects.py`. Pure function.
2. Register it in the `DIALECTS` mapping in the same file, with a human-readable label.
3. Add table-driven cases to `tests/test_dialects.py`.

The template builds its radio group from `DIALECTS` and `views.py` looks the choice up in the same
mapping, so nothing else needs editing. If adding a dialect requires touching `views.py`, the
registry is being bypassed.

## User-friendly by default

The user is a musician with a file exported from MuseScore and no interest in how this works.
Every decision about the visible surface follows from that.

- **Zero required choices.** Uploading a file and pressing one button must produce a correct
  colinha. Dialect, base octave, and part all have defaults that are right for the common case;
  overrides are there, but never in the way.
- **Plain words.** No "MusicXML parse error", "part index", "413", or exception class names on the
  page. Say "score", "instrument", "file too large". Domain terms the musicians already use
  (colinha, solfège) are fine.
- **Every error message answers three things:** what went wrong, in the user's terms; which file
  it concerns (name it); and what to do next. "Could not read *song.mscz*. This is a MuseScore
  project file — open it in MuseScore and use *File → Export → MusicXML*, then upload that
  instead." — not "Unsupported file type".
- **Keep the user's work.** When a conversion fails, re-render the form with their dialect,
  octave, and part choices still selected. Never make them start over.
- **Nothing to manage.** No terminal window left open, no process to kill, no files to clean up.
  A second click on the icon opens a tab; walking away shuts it down.
- The launcher is the one place a failure can happen with no page to show it on. There, show a
  native dialog (`tkinter.messagebox` ships with the Windows Python installer) with the same
  three-part message, not a console that flashes and vanishes.

## Human errors are the main test surface

Wrong input is the normal case for this app, not the edge case. The mistakes it handles are listed
once, in the **Error catalogue** in `PLAN.md`, each with an ID (`E01`, `E02`, …), the module that
catches it, and its message. That table is the single source of truth — do not copy it here or
anywhere else; refer to entries by ID.

Every catalogue entry has a test that asserts the **exact user-facing message** (or a stable
fragment of it), that the response is a rendered page rather than a traceback, and that the user's
form choices survived. Put them in one parametrized test per layer (`test_views.py` for upload
cases, `test_launcher.py` for launcher cases), with the catalogue ID as the test case id
(`pytest.param(..., id="E02")`), so each row maps to exactly one test and `pytest -k E02` finds it.

When a real user hits a mistake not in the catalogue, add a row to `PLAN.md` with the next free ID
and a failing test before fixing it. When a message's wording changes, change it in the catalogue
and the test together.

`ScoreError` carries a user-facing message, written where the failure is understood (in
`parsing.py`). `views.py` renders that message; it does not compose its own from exception text.
Never show `str(exc)` from a third-party library to the user — log it, and show the plain message.

## Test fixtures

`tests/fixtures/` is split into pairs: `input/<name>.xml` and the expected result in
`output/<name>.txt`, or `output/<name>.error` for an input that is expected to fail. One fixture,
one concern: accidentals, octave casing, multiple sections, no rehearsal mark, ties and rests.

A tied note needs `<tie type="…"/>` (the sound element, which music21 reads) as well as
`<notations><tied/></notations>` (the drawing, which it ignores) — MuseScore writes both, and a
fixture with only `<tied>` silently tests nothing.

Inputs are **hand-authored** minimal MusicXML — a few measures each, written for this project. Do
not copy real scores in; they are large, they drown the case under test, and their licensing is
someone else's.

Prefer asserting the final rendered text end to end over poking at intermediate objects — the text
is what the user actually gets. Compare as UTF-8 text with normalized line endings, so the same
test passes on Windows.

## Clean code and Python practice

- **Python 3.12+**, `src/` layout, everything declared in `pyproject.toml`. No `requirements.txt`
  alongside it.
- `ruff` for linting and formatting, `mypy --strict` for types; both run clean before a change is
  done. Configure them in `pyproject.toml`, not in separate dotfiles.
- Type-annotate every function signature. Prefer `frozen=True` dataclasses over dicts and tuples
  for anything crossing a module boundary. `Enum` over magic strings for closed sets.
- Small functions that do one thing, named with the domain vocabulary above. If a function needs a
  comment explaining *what* it does, it needs a better name or a split; comments explain *why*.
- Docstrings on public functions, one line unless the behaviour genuinely needs more.
- No bare `except:` and no `except Exception` outside the single top-level handler in the shell
  that turns an unexpected error into a friendly page plus a logged traceback.
- `logging`, never `print`, in the shell. The pure core does not log.
- Constants at module top in `UPPER_CASE`; no mutable default arguments; no module-level side
  effects beyond definitions — the app is built in `create_app()`, not at import time.
- Write the test first when fixing a bug: a failing test that reproduces it, then the fix.

## Windows is the target platform

Code is written on Linux and shipped to Windows. These rules keep it portable:

- **`pathlib.Path` for every path**, never string concatenation with `/`. Per-user locations come
  from `platformdirs` (`user_log_dir("notation_service")`), never a hardcoded `~/.cache`.
- **Always pass `encoding="utf-8"`** when opening text. Windows' default is `cp1252`, which cannot
  hold `♭`, `↑`, or `ré`. The download is served as `text/plain; charset=utf-8`.
- **Temp files:** a `NamedTemporaryFile` that is still open cannot be reopened by name on Windows.
  Create it with `delete=False`, write, close, parse, and `unlink` in the `finally`.
- **No POSIX-only process calls.** No `signal.SIGTERM` for shutdown, no `start_new_session`
  without its Windows counterpart. The launcher spawns the server detached with no console
  window (`DETACHED_PROCESS | CREATE_NO_WINDOW` on Windows); isolate that branch in one function.
- **No console windows.** The icon's entry point is a `[project.gui-scripts]` entry, so Windows
  builds it as a windowless `.exe`.
- The icon ships as `.ico` for Windows alongside the `.svg`.
- Keep platform branches (`sys.platform == "win32"`) inside the shell, few, and each covered by a
  test that runs on both platforms or is explicitly skipped on one with a reason.

### How it is tested from Linux

Three layers, cheapest first:

1. **Every change, locally on Linux:** `pytest`, `ruff`, `mypy`. Also run the suite once with
   `PYTHONUTF8=0 LC_ALL=C` to flush out code that silently relies on a UTF-8 default encoding.
2. **Every push, CI on real Windows:** a GitHub Actions matrix of `ubuntu-latest` and
   `windows-latest` running the same commands. This is the check that actually proves Windows
   compatibility; a Windows-only failure blocks the change like any other.
3. **Before handing a build to users, a Windows VM:** install, click the icon, convert a file,
   click again, leave it idle, uninstall — the checklist in `PLAN.md` *Verification*. On Manjaro,
   `quickemu` (`quickget windows 11`) produces a working VM without a licence key. Wine is not a
   substitute; it does not behave like Windows for venvs, process spawning, or shortcuts.

## Running

For development on Linux:

```sh
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest                               # tests
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy src
.venv/bin/python -m notation_service.server    # serve in the foreground
.venv/bin/notation-service                     # what the icon runs: start-or-attach, open browser
```

The Windows install and uninstall steps are defined in `PLAN.md` and must be safe to re-run.

Configuration is environment-driven, read once into `Config`: `NOTATION_PORT` (5117),
`NOTATION_IDLE_MINUTES` (20), `NOTATION_MAX_UPLOAD_MB` (10). The server log lives in
`platformdirs.user_log_dir("notation_service")` — on Windows,
`%LOCALAPPDATA%\notation_service\Logs\server.log`; on Linux,
`~/.local/state/notation_service/log/server.log`.

## Conventions

- Failures reaching the user are plain-language messages rendered into the page. A traceback in
  the browser is a bug — see *Human errors are the main test surface*.
- The app writes nothing persistent. Uploads go to a `tempfile` and are removed in a `finally`.
  There is no database, no session, no uploads directory, no job queue. Keep it that way; it is
  the reason this is hard to break.
- The server binds `127.0.0.1` only. It has no authentication. Do not change the binding unless
  the user asks for it.
- No CDN links in templates. CSS is vendored into `static/` so the app works offline.
