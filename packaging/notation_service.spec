# PyInstaller one-folder build. Run from the repository root:
#   pyinstaller --noconfirm packaging/notation_service.spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).parent
package = root / "src" / "notation_service"

analysis = Analysis(
    [str(root / "packaging" / "entry.py")],
    pathex=[str(root / "src")],
    datas=[
        (str(package / "templates"), "notation_service/templates"),
        (str(package / "static"), "notation_service/static"),
    ],
    # The server is only imported when the launcher is given --server.
    hiddenimports=["notation_service.server", *collect_submodules("waitress")],
    # Optional music21 extra for plotting; this app never draws graphs.
    excludes=["matplotlib"],
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    exclude_binaries=True,
    name="notation_service",
    console=False,  # no console window, for the launcher and the server alike
    icon=str(root / "assets" / "icon.ico"),
)
coll = COLLECT(exe, analysis.binaries, analysis.datas, name="notation_service")
