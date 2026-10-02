# Colinha converter

Turns a score exported from MuseScore into a **colinha**: just the note names, one line per
measure.

## Install (Windows)

### Download the installer

1. Go to the [GitHub Actions runs](https://github.com/vlam94/notation_service/actions) page.
2. Click on the most recent successful run (look for a green checkmark) titled "CI".
3. Scroll down to the **Artifacts** section and click **notation_service-setup** to download
   `notation_service-setup.exe`.

   Alternatively, to get the latest build from a specific branch or commit:
   - Find the run in the Actions list
   - Look for its **name** in the workflow run title (shows the branch, e.g., "main")
   - Download the artifact from that run

   *Note:* the installer is built on every push to the repository. If you don't see artifacts,
   the build may still be in progress — wait a moment and refresh.

### Run the installer

1. Double-click `notation_service-setup.exe`. Windows may say *"Windows protected your PC"* —
   this is because the installer is not signed. Click **More info**, then **Run anyway**.
   <!-- screenshot: SmartScreen dialog with "More info" and "Run anyway" -->
2. Follow the installer. It does not need an administrator password. Tick *Create a desktop
   shortcut* if you want an icon on the desktop.

## Use

1. In MuseScore, open your score and choose **File → Export → MusicXML**.
2. Click the **Notation Converter** icon. Your browser opens the converter.
3. Choose the exported file and press **Convert**.
4. Press **Copy** or **Download .txt** to take the colinha with you.

Under **Options** you can pick the notation (solfège *dó ré mi* or letters *C D E*), the base
octave, and — for a score with several instruments — which instrument to write out.

There is nothing to close when you are done: the converter stops by itself after 20 minutes
without use. Clicking the icon again opens a new tab.

## Uninstall

**Settings → Apps → Installed apps → Notation Converter → Uninstall.**

## If something goes wrong

The converter keeps a log at `%LOCALAPPDATA%\notation_service\Logs\server.log`. Send that file
along with the score when reporting a problem.

---

## Development

Linux, Python 3.12+. Conventions are in `CLAUDE.md`; the design is in `PLAN.md`.

```sh
python -m venv .venv && .venv/bin/pip install -e '.[dev]'
scripts/check.sh                              # every automated check, one PASS/FAIL line each
.venv/bin/python -m notation_service.server   # serve in the foreground on http://127.0.0.1:5117
.venv/bin/notation-service                    # what the icon runs: start-or-attach, open browser
```

The Windows installer is built by CI (`build-windows` job) and attached to each run as the
`notation_service-setup` artifact. To build the bundle locally:
`pip install -e '.[build]' && pyinstaller --noconfirm packaging/notation_service.spec`.
