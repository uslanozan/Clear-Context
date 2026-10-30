from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)

from clear_context.domain.investigation import (
    InvestigationReport,
    InvestigationStatus,
    ResearchMode,
)
from clear_context.schemas.investigation import InvestigationCreate, InvestigationView, StepView
from clear_context.services import media as media_service

router = APIRouter()


@router.post("/investigations", status_code=202, response_model=InvestigationView)
def create_investigation(
    payload: InvestigationCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    response: Response,
):
    row = request.app.state.repository.create(
        payload.text, mode=request.app.state.mode, research_mode=payload.research_mode
    )
    background_tasks.add_task(request.app.state.service.run, UUID(row.id))
    response.headers["Location"] = f"/api/investigations/{row.id}"
    return row


@router.post("/investigations/upload", status_code=202, response_model=InvestigationView)
async def create_investigation_with_media(
    background_tasks: BackgroundTasks,
    request: Request,
    response: Response,
    files: Annotated[list[UploadFile], File()],
    text: Annotated[str, Form(max_length=20000)] = "",
    research_mode: Annotated[ResearchMode, Form()] = "balanced",
):
    """Start an investigation from images (and optional caption text) in one request."""
    uploads, total = [], 0
    for upload in files:
        # Read one byte past the largest limit so oversized files are rejected, not truncated.
        data = await upload.read(media_service.VIDEO_LIMIT + 1)
        total += len(data)
        if total > media_service.TOTAL_LIMIT:
            raise HTTPException(status_code=422, detail="Attached files exceed 100 MB in total.")
        uploads.append((upload.filename or "upload", data))
    try:
        checked = media_service.validate(uploads)
    except media_service.MediaRejected as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    text = text.strip()
    if not text and not any(kind == "image" for _, kind, _, _ in checked):
        raise HTTPException(
            status_code=422,
            detail="Add text or an image; video analysis is not connected yet.",
        )
    stored = [
        media_service.store(request.app.state.media_dir, name, kind, mime_type, data)
        for name, kind, mime_type, data in checked
    ]
    row = request.app.state.repository.create(
        text, mode=request.app.state.mode, research_mode=research_mode, media=stored
    )
    background_tasks.add_task(request.app.state.service.run, UUID(row.id))
    response.headers["Location"] = f"/api/investigations/{row.id}"
    return row


@router.get("/investigations", response_model=list[InvestigationView])
def list_investigations(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return request.app.state.repository.list_recent(limit, offset)


def require_investigation(request: Request, investigation_id: UUID):
    row = request.app.state.repository.get(investigation_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return row


@router.get("/investigations/{investigation_id}", response_model=InvestigationView)
def get_investigation(request: Request, investigation_id: UUID):
    return require_investigation(request, investigation_id)


@router.get("/investigations/{investigation_id}/steps", response_model=list[StepView])
def get_steps(request: Request, investigation_id: UUID):
    require_investigation(request, investigation_id)
    return request.app.state.repository.steps(investigation_id)


@router.get("/investigations/{investigation_id}/report", response_model=InvestigationReport)
def get_report(request: Request, investigation_id: UUID):
    row = require_investigation(request, investigation_id)
    if row.status != InvestigationStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Investigation report is not available.")
    return request.app.state.repository.get_report(investigation_id)
