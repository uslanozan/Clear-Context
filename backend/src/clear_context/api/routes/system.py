from fastapi import APIRouter, Request

from clear_context import __version__
from clear_context.core.settings import load_model_catalog

router = APIRouter()


@router.get("/health")
def health(request: Request):
    runtime = request.app.state.service.runtime
    return {
        "status": "ok",
        "version": __version__,
        "mode": runtime.mode,
        "paid_api_calls_enabled": runtime.mode == "meta",
        "research_enabled": runtime.research_enabled,
        "default_research_mode": runtime.settings.default_research_mode,
    }


@router.get("/models")
def model_selection(request: Request):
    runtime = request.app.state.service.runtime
    return {"mode": runtime.mode, "configured_models": runtime.models}


@router.get("/prices")
def model_prices(request: Request):
    """List prices per million tokens for catalog models, to estimate a report's cost."""
    catalog = load_model_catalog(request.app.state.service.runtime.settings)
    prices = {}
    for model in catalog.models.values():
        price = model.price or {}
        if model.api_model_id and price.get("unit") == "million_tokens":
            prices[model.api_model_id] = {
                "input": price["input"],
                "cached_input": price.get("cached_input"),
                "output": price["output"],
            }
    return {
        "currency": catalog.currency,
        "checked_on": catalog.checked_on,
        "per_million_tokens": prices,
    }
