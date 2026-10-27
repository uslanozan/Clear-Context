"""Export diagram HTML with the installed Diagram Design helpers."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent.parent
SKILL = Path.home() / ".codex/skills/diagram-design"
font_path = (
    ROOT
    / "frontend/node_modules/@fontsource-variable/source-sans-3/files/source-sans-3-latin-wght-normal.woff2"
)
font = base64.b64encode(font_path.read_bytes()).decode()
font_css = (
    "@font-face{font-family:'Source Sans 3';src:url(data:font/woff2;base64,"
    + font
    + ") format('woff2');font-weight:200 900;font-style:normal;}"
)
environment = os.environ.copy()
local_tools = ROOT / ".local/diagram-tools"
if local_tools.is_dir():
    environment["PYTHONPATH"] = (
        str(local_tools) + os.pathsep + environment.get("PYTHONPATH", "")
    )


def export(source: Path) -> None:
    subprocess.run(
        [sys.executable, str(SKILL / "scripts/self_check.py"), str(source)], check=True
    )
    vector = OUT / "svg" / (source.stem + ".svg")
    subprocess.run(
        [
            sys.executable,
            str(SKILL / "scripts/export_svg.py"),
            str(source),
            str(vector),
            "--system-fonts",
        ],
        check=True,
    )
    # Preserve the approved local font without adding a network dependency.
    svg = vector.read_text(encoding="utf-8")
    svg = svg.replace("<defs>", "<defs><style>" + font_css + "</style>", 1)
    vector.write_text(svg, encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(SKILL / "scripts/export_png.py"),
            str(source),
            str(OUT / "png" / (source.stem + ".png")),
            "2",
        ],
        env=environment,
        check=True,
    )
    print("Exported", source.stem, flush=True)


if __name__ == "__main__":
    for folder in ["svg", "png"]:
        (OUT / folder).mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(export, sorted((OUT / "html").glob("0*.html"))))
