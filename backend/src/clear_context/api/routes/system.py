from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request):
    runtime = request.app.state.service.runtime
    return {
        "status": "ok",
        "mode": runtime.mode,
        "paid_api_calls_enabled": runtime.mode == "meta",
        "research_enabled": runtime.research_enabled,
        "default_research_mode": runtime.settings.default_research_mode,
    }


@router.get("/models")
def model_selection(request: Request):
    runtime = request.app.state.service.runtime
    return {"mode": runtime.mode, "configured_models": runtime.models}
