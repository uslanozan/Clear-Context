"""Desktop entry point: start the local server and open Clear Context in the browser."""

import json
import os
import socket
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from clear_context.core.settings import PROJECT_ROOT, Settings, resolve_path
from clear_context.main import create_app

HOST = "127.0.0.1"
# The Chrome extension looks for the desktop app on this port.
DEFAULT_PORT = 8765
PORT_ATTEMPTS = 10


def clear_context_health(port: int) -> dict | None:
    """The health answer of a Clear Context server on this port, or None."""
    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/health", timeout=1) as response:
            body = json.load(response)
    except (OSError, ValueError):
        return None
    return body if isinstance(body, dict) and body.get("status") == "ok" else None


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((HOST, port))
        except OSError:
            return False
    return True


def open_when_ready(url: str, port: int, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if clear_context_health(port):
            webbrowser.open(url)
            return
        time.sleep(0.3)


def main() -> None:
    first_port = int(os.environ.get("CLEAR_CONTEXT_PORT", DEFAULT_PORT))
    for port in range(first_port, first_port + PORT_ATTEMPTS):
        url = f"http://{HOST}:{port}/"
        if clear_context_health(port):
            # Already running, for example after a second double-click: just show it.
            print(f"Clear Context is already running at {url}")
            webbrowser.open(url)
            return
        if port_is_free(port):
            break
    else:
        raise SystemExit(f"No free port between {first_port} and {port}.")

    # The desktop build bundles the web app as web/; from a checkout, use the Vite build.
    web = PROJECT_ROOT / "web"
    settings = Settings(
        api_host=HOST,
        api_port=port,
        auto_migrate=True,
        web_dist_dir=web if web.is_dir() else PROJECT_ROOT / "frontend" / "dist",
    )
    print(f"Clear Context is running at {url}", flush=True)
    print(f"Your data is stored in {resolve_path(settings.database_path).parent}", flush=True)
    print("Keep this window open while you use it; close it to stop Clear Context.", flush=True)
    threading.Thread(target=open_when_ready, args=(url, port), daemon=True).start()
    uvicorn.run(create_app(settings), host=HOST, port=port, log_level="warning", workers=1)


if __name__ == "__main__":
    main()
