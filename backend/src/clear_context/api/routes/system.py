from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request):
    return {
        "status": "ok",
        "mode": request.app.state.mode,
        "paid_api_calls_enabled": request.app.state.mode == "meta",
    }


@router.get("/models")
def model_selection(request: Request):
    return {"mode": request.app.state.mode, "configured_models": request.app.state.models}
