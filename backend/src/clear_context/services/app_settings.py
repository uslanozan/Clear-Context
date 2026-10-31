"""Panel settings: seeded from .env, then kept in the database.

At start-up every panel field without a stored value gets its .env value, so the database
holds the settings from then on. Later .env edits do not change a stored value; the panel marks
values that differ from the current .env and can copy the .env value again.
"""

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
PANEL_FIELDS = (
    *SECRET_FIELDS,
    *DIRECT_FIELDS,
    "paid_calls",
    "reverse_image_search",
    "fact_check_search",
)


class SettingsNotUsable(ValueError):
    """The combined settings cannot run; the message is safe to show."""


def paid_calls(settings: Settings) -> bool:
    return settings.app_mode == "meta" and settings.allow_paid_api_calls


def env_values(base: Settings) -> dict[str, object]:
    """Panel fields as .env sets them: the seed and the target of "Use .env value"."""
    catalog = load_model_catalog(base)
    fallback = base.model_default.strip() or catalog.defaults.model
    values: dict[str, object] = {
        name: getattr(base, name).get_secret_value() for name in SECRET_FIELDS
    }
    for task in MODEL_TASKS:
        values[f"model_{task}"] = getattr(base, f"model_{task}").strip() or fallback
    values.update(
        paid_calls=paid_calls(base),
        default_research_mode=base.default_research_mode,
        reverse_image_search=base.reverse_image_provider != "none",
        fact_check_search=base.fact_check_image_search,
        link_reading=base.link_reading,
        search_min_score=base.search_min_score,
    )
    return values


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
            # Preview mode makes no paid calls. When .env already allows them, it also decides
            # source research; turning paid calls on here turns research on with them.
            update["app_mode"] = "meta" if value else "mock"
            update["allow_paid_api_calls"] = bool(value)
            update["research_enabled"] = base.research_enabled if paid_calls(base) else bool(value)
    settings = base.model_copy(update=update)
    if settings.app_mode == "meta" and not settings.meta_api_key.get_secret_value().strip():
        raise SettingsNotUsable("Paid calls need a Meta API key. Add the key first.")
    if settings.app_mode == "meta" and not settings.allow_paid_api_calls:
        raise SettingsNotUsable("Meta mode in .env needs ALLOW_PAID_API_CALLS=true.")
    return settings


def differs_from_env(stored: dict[str, object], env: dict[str, object]) -> list[str]:
    return sorted(key for key in PANEL_FIELDS if key in stored and stored[key] != env[key])


def key_preview(value: str) -> str | None:
    """First eight and last four characters, like provider dashboards; less for short keys."""
    if len(value) >= 24:
        return f"{value[:8]}...{value[-4:]}"
    if len(value) >= 16:
        return f"...{value[-4:]}"
    return None


def key_status(value: str, differs: bool) -> KeyStatus:
    if not value:
        return KeyStatus(configured=False)
    return KeyStatus(
        configured=True,
        preview=key_preview(value),
        source="panel" if differs else "env",
    )


def settings_view(
    settings: Settings, stored: dict[str, object], env: dict[str, object], error: str | None
) -> SettingsView:
    catalog = load_model_catalog(settings)
    fallback = settings.model_default.strip() or catalog.defaults.model
    changed = differs_from_env(stored, env)
    keys = {
        name: key_status(getattr(settings, name).get_secret_value(), name in changed)
        for name in SECRET_FIELDS
    }
    return SettingsView(
        keys=keys,
        paid_calls=paid_calls(settings),
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
        changed=changed,
        error=error,
    )
