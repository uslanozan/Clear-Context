from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

router = APIRouter()


@router.get("/media/{media_id}")
def get_media(media_id: UUID, request: Request):
    row = request.app.state.repository.media(media_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Media not found.")
    # Files are addressed by their stored hash name, never by a client-supplied path.
    path = request.app.state.media_dir / row.storage_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Media file is missing.")
    return FileResponse(
        path,
        media_type=row.mime_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"},
    )
