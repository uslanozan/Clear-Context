"""Start a built desktop bundle with empty data, run one preview investigation, then stop it.

Usage: python packaging/desktop/smoke_test.py "dist/Clear Context"
Preview mode makes no model or search calls; no keys are needed or read.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

PORT = 8799


def call(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}",
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def wait_for(check, seconds: float, what: str):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            result = check()
            if result:
                return result
        except OSError:
            pass
        time.sleep(0.5)
    raise SystemExit(f"Timed out waiting for {what}.")


def main() -> None:
    bundle = Path(sys.argv[1])
    executable = bundle / ("Clear Context.exe" if os.name == "nt" else "Clear Context")
    with tempfile.TemporaryDirectory() as home:
        env = {
            **os.environ,
            # Every platform's data folder points into the empty temporary home.
            "APPDATA": home,
            "HOME": home,
            "XDG_DATA_HOME": home,
            "CLEAR_CONTEXT_PORT": str(PORT),
            # Keep the launcher from opening a real browser.
            "BROWSER": "no-such-browser-for-smoke-tests",
        }
        process = subprocess.Popen([str(executable)], env=env)
        try:
            health = wait_for(lambda: call("/api/health"), 90, "the server to start")
            assert health["mode"] == "mock", health
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/", timeout=5) as page:
                assert b"<title>" in page.read(), "The web app is not served."
            created = call(
                "/api/investigations", {"text": "The Eiffel Tower is in Paris."}
            )
            finished = wait_for(
                lambda: (
                    (row := call(f"/api/investigations/{created['id']}"))["status"]
                    in {"completed", "failed"}
                    and row
                ),
                60,
                "the investigation to finish",
            )
            assert finished["status"] == "completed", finished
            report = call(f"/api/investigations/{created['id']}/report")
            assert report["claims"], report
            print(
                "Desktop smoke test passed: server, web app, migrations and a preview run."
            )
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
