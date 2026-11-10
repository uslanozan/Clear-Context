# PyInstaller spec for the Clear Context desktop app.
# Build the web app first (npm run build in frontend/), then from the repository root:
#   python -m PyInstaller packaging/desktop/clear-context.spec --noconfirm
# The bundle keeps the repository layout (config/, backend/migrations) and adds web/.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

here = Path(SPECPATH).resolve()
root = here.parents[1]
web = root / "frontend" / "dist"
if not (web / "index.html").is_file():
    raise SystemExit("Build the web app first: npm run build in frontend/.")

datas = [
    (str(root / "config"), "config"),
    (str(root / "backend" / "alembic.ini"), "backend"),
    (str(root / "backend" / "migrations"), "backend/migrations"),
    (str(web), "web"),
    (str(root / "LICENSE"), "."),
    # Language profiles are read from files at run time.
    *collect_data_files("langdetect"),
]
# Alembic loads env.py and the migration scripts from files, and uvicorn picks its
# protocol and loop implementations by name, so their modules are listed explicitly.
hiddenimports = [*collect_submodules("clear_context"), *collect_submodules("uvicorn")]

a = Analysis(
    [str(here / "launcher.py")],
    pathex=[str(root / "backend" / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "ruff", "IPython"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Clear Context",
    # The console window shows the address and stops the server when it is closed.
    console=True,
    icon=str(root / "frontend" / "public" / "brand" / "clear-context-mark.png"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Clear Context")
