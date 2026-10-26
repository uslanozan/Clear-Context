from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response

from clear_context.domain.investigation import InvestigationReport, InvestigationStatus
from clear_context.schemas.investigation import InvestigationCreate, InvestigationView, StepView

router = APIRouter()


@router.post("/investigations", status_code=202, response_model=InvestigationView)
def create_investigation(
    payload: InvestigationCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    response: Response,
):
    row = request.app.state.repository.create(payload.text, mode=request.app.state.mode)
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
