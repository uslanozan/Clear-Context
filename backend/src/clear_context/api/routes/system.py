from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "mode": "mock", "paid_api_calls_enabled": False}


@router.get("/models")
def model_selection(request: Request):
    return {"mode": "mock", "configured_models": request.app.state.models}
