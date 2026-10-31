import threading

from fastapi import APIRouter, HTTPException, Request

from clear_context.schemas.settings import SettingsUpdate, SettingsView
from clear_context.services.app_settings import effective_settings, settings_view
from clear_context.services.runtime import build_runtime

router = APIRouter()
# One change at a time, so two saves cannot interleave stored values and providers.
update_lock = threading.Lock()


@router.get("/settings", response_model=SettingsView)
def get_settings(request: Request):
    """Current settings. API keys are reported as configured or not, never returned."""
    state = request.app.state
    return settings_view(
        state.service.runtime.settings, state.settings_repository.load(), state.settings_error
    )


@router.put("/settings", response_model=SettingsView)
def update_settings(payload: SettingsUpdate, request: Request):
    """Save changed values; the next investigation uses them, without a restart."""
    state = request.app.state
    changes = payload.changes()
    with update_lock:
        stored = {
            key: value
            for key, value in {**state.settings_repository.load(), **changes}.items()
            if value is not None
        }
        try:
            settings = effective_settings(state.base_settings, stored)
            runtime = build_runtime(settings, state.research_workspace)
        except ValueError as error:
            # Messages name the setting at fault, never its value.
            raise HTTPException(status_code=422, detail=str(error)[:300]) from None
        state.settings_repository.save(changes)
        state.service.replace_runtime(runtime)
        state.settings_error = None
    return settings_view(settings, stored, None)
