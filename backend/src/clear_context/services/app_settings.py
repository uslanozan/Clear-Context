"""Settings changed in the panel, applied over the .env settings."""

from pydantic import SecretStr

from clear_context.core.settings import Settings, load_model_catalog, text_model_allowed
from clear_context.schemas.settings import KeyStatus, ModelOption, SettingsView

SECRET_FIELDS = ("meta_api_key", "tavily_api_key", "serp_api_key", "google_fact_check_api_key")
MODEL_TASKS = ("claim_extraction", "screenshot", "research", "judge")
DIRECT_FIELDS = (
    *(f"model_{task}" for task in MODEL_TASKS),
    "default_research_mode",
    "link_reading",
    "search_min_score",
)


class SettingsNotUsable(ValueError):
    """The combined settings cannot run; the message is safe to show."""


def effective_settings(base: Settings, stored: dict[str, object]) -> Settings:
    update: dict[str, object] = {}
    for key, value in stored.items():
        if key in SECRET_FIELDS:
            update[key] = SecretStr(str(value))
        elif key in DIRECT_FIELDS:
            update[key] = value
        elif key == "fact_check_search":
            update["fact_check_image_search"] = bool(value)
        elif key == "reverse_image_search":
            configured = base.reverse_image_provider
            on = configured if configured != "none" else "serpapi_lens"
            update["reverse_image_provider"] = on if value else "none"
        elif key == "paid_calls":
            # Preview mode makes no paid calls; live mode also runs source research.
            update["app_mode"] = "meta" if value else "mock"
            update["allow_paid_api_calls"] = bool(value)
            update["research_enabled"] = bool(value) or base.research_enabled
    settings = base.model_copy(update=update)
    if settings.app_mode == "meta" and not settings.meta_api_key.get_secret_value().strip():
        raise SettingsNotUsable("Paid calls need a Meta API key. Add the key first.")
    if settings.app_mode == "meta" and not settings.allow_paid_api_calls:
        raise SettingsNotUsable("Meta mode in .env needs ALLOW_PAID_API_CALLS=true.")
    return settings


def key_status(value: str, from_panel: bool) -> KeyStatus:
    if not value:
        return KeyStatus(configured=False)
    return KeyStatus(
        configured=True,
        ending=value[-4:] if len(value) >= 16 else None,
        source="panel" if from_panel else "env",
    )


def settings_view(settings: Settings, stored: dict[str, object], error: str | None) -> SettingsView:
    catalog = load_model_catalog(settings)
    fallback = settings.model_default.strip() or catalog.defaults.model
    keys = {
        name: key_status(getattr(settings, name).get_secret_value(), name in stored)
        for name in SECRET_FIELDS
    }
    return SettingsView(
        keys=keys,
        paid_calls=settings.app_mode == "meta" and settings.allow_paid_api_calls,
        models={
            task: getattr(settings, f"model_{task}").strip() or fallback for task in MODEL_TASKS
        },
        model_options=[
            ModelOption(alias=alias, name=model.name)
            for alias, model in catalog.models.items()
            if text_model_allowed(model, settings)
        ],
        default_research_mode=settings.default_research_mode,
        reverse_image_search=settings.reverse_image_provider != "none",
        fact_check_search=settings.fact_check_image_search,
        link_reading=settings.link_reading,
        search_min_score=settings.search_min_score,
        changed=sorted(stored),
        error=error,
    )
