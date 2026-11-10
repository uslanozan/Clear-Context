"""Serves the built web app beside the API, as nginx does in the Docker setup."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}
NO_CACHE = {"Cache-Control": "no-cache"}


def mount_web_app(app: FastAPI, dist: Path) -> None:
    root = dist.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"The built web app was not found at {root}.")

    # Registered after the API routes, so it only answers paths they do not match.
    @app.get("/{path:path}", include_in_schema=False)
    def web_app(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found.")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            # Hashed build assets never change under the same name.
            hashed = candidate.is_relative_to(root / "assets")
            return FileResponse(candidate, headers=IMMUTABLE if hashed else NO_CACHE)
        if path.startswith("assets/"):
            raise HTTPException(status_code=404, detail="Not found.")
        # Any other address is a client-side route of the single-page app.
        return FileResponse(index, headers=NO_CACHE)
