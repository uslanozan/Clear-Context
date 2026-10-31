from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Printable characters without spaces, so a key cannot carry a header break.
ApiKey = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[!-~]{8,500}$")]
# complete mode is started only from a report, after a confirmation; never a default.
DefaultMode = Literal["fast", "balanced", "deep"]
ModelAlias = Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,60}$")]


class SettingsUpdate(BaseModel):
    """Changed panel values. A field set to null takes the current .env value again; omitted
    fields stay as they are. API keys are write-only."""

    model_config = ConfigDict(extra="forbid")
    meta_api_key: ApiKey | None = None
    tavily_api_key: ApiKey | None = None
    serp_api_key: ApiKey | None = None
    google_fact_check_api_key: ApiKey | None = None
    model_claim_extraction: ModelAlias | None = None
    model_screenshot: ModelAlias | None = None
    model_research: ModelAlias | None = None
    model_judge: ModelAlias | None = None
    paid_calls: bool | None = None
    default_research_mode: DefaultMode | None = None
    reverse_image_search: bool | None = None
    fact_check_search: bool | None = None
    link_reading: bool | None = None
    search_min_score: float | None = Field(default=None, ge=0, le=1)

    def changes(self) -> dict[str, object | None]:
        return {name: getattr(self, name) for name in self.model_fields_set}


class KeyStatus(BaseModel):
    configured: bool
    # Start and end of a long key ("LLM_2896...XkQs"), so keys can be told apart; never the key.
    preview: str | None = None
    # "env" when the saved key equals the current .env key, "panel" when it differs.
    source: Literal["panel", "env"] | None = None


class ModelOption(BaseModel):
    alias: str
    name: str


class SettingsView(BaseModel):
    keys: dict[str, KeyStatus]
    paid_calls: bool
    models: dict[str, str]
    model_options: list[ModelOption]
    default_research_mode: DefaultMode
    reverse_image_search: bool
    fact_check_search: bool
    link_reading: bool
    search_min_score: float
    # Fields whose saved value differs from the current .env value.
    changed: list[str]
    # Saved panel values that could not be applied when the server started.
    error: str | None = None
