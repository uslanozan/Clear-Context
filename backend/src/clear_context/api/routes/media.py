import re
from uuid import UUID

import av
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from clear_context.services.playable_video import playable

router = APIRouter()


FRAME_NAME = re.compile(r"[0-9a-f]{64}\.jpg")
HEADERS = {"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"}


def stored_file(request: Request, storage_name: str):
    # Files are addressed by their stored hash name, never by a client-supplied path.
    path = request.app.state.media_dir / storage_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Media file is missing.")
    return path


@router.get("/media/{media_id}")
def get_media(media_id: UUID, request: Request):
    row = request.app.state.repository.media(media_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Media not found.")
    return FileResponse(
        stored_file(request, row.storage_name), media_type=row.mime_type, headers=HEADERS
    )


@router.get("/media/{media_id}/playable")
def get_playable(media_id: UUID, request: Request):
    """A video the browser can show: the upload itself, or a WebM copy made on first request."""
    row = request.app.state.repository.media(media_id)
    if row is None or row.kind != "video":
        raise HTTPException(status_code=404, detail="Video not found.")
    try:
        path, media_type = playable(stored_file(request, row.storage_name))
    except (OSError, ValueError, av.FFmpegError) as error:
        raise HTTPException(
            status_code=422, detail="This video could not be prepared for playback."
        ) from error
    return FileResponse(path, media_type=media_type, headers=HEADERS)


@router.get("/media/{media_id}/frames/{index}")
def get_frame(media_id: UUID, index: int, request: Request):
    """A frame taken from a video during its check, by its position in the report."""
    row = request.app.state.repository.media(media_id)
    frames = ((row.finding or {}).get("frames") or []) if row else []
    if not 0 <= index < len(frames) or not FRAME_NAME.fullmatch(
        str(frames[index].get("storage_name", ""))
    ):
        raise HTTPException(status_code=404, detail="Frame not found.")
    return FileResponse(
        stored_file(request, frames[index]["storage_name"]),
        media_type="image/jpeg",
        headers=HEADERS,
    )
