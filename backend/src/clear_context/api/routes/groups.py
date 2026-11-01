from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from clear_context.repositories.history_group import MAX_GROUPS
from clear_context.schemas.history_group import GroupAssignment, GroupName, GroupView

router = APIRouter()


@router.get("/groups", response_model=list[GroupView])
def list_groups(request: Request):
    return request.app.state.groups.list()


@router.post("/groups", response_model=GroupView, status_code=201)
def create_group(payload: GroupName, request: Request):
    row = request.app.state.groups.create(payload.name)
    if row is None:
        raise HTTPException(status_code=409, detail=f"At most {MAX_GROUPS} groups.")
    return row


@router.patch("/groups/{group_id}", response_model=GroupView)
def rename_group(group_id: UUID, payload: GroupName, request: Request):
    row = request.app.state.groups.rename(group_id, payload.name)
    if row is None:
        raise HTTPException(status_code=404, detail="Group not found.")
    return row


@router.delete("/groups/{group_id}", status_code=204)
def delete_group(group_id: UUID, request: Request):
    if not request.app.state.groups.delete(group_id):
        raise HTTPException(status_code=404, detail="Group not found.")
    return Response(status_code=204)


@router.put("/investigations/{investigation_id}/group", status_code=204)
def assign_group(investigation_id: UUID, payload: GroupAssignment, request: Request):
    result = request.app.state.groups.assign(investigation_id, payload.group_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    if result is False:
        raise HTTPException(status_code=404, detail="Group not found.")
    return Response(status_code=204)
