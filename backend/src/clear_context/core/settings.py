from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TASKS = ("claim_extraction", "screenshot", "research", "judge", "report")
TEXT_MODELS = {
    "muse-wonder-1.0",
    "muse-spark-1.3",
    "muse-spark-1.2",
    "muse-spark-1.1",
    "muse-spark-1.3-contributor",
    "muse-spark-1.2-contributor",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", extra="ignore", hide_input_in_errors=True
    )

    app_mode: Literal["mock", "meta"] = "mock"
    allow_paid_api_calls: bool = False
    research_enabled: bool = False
    meta_timeout_seconds: float = Field(default=60, gt=0, le=120)
    meta_max_completion_tokens: int = Field(default=4096, ge=128, le=4096)
    meta_max_claims: int = Field(default=8, ge=1, le=12)
    graph_recursion_limit: int = Field(default=12, ge=4, le=100)
    api_host: str = Field(default="127.0.0.1", min_length=1)
    api_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["critical", "error", "warning", "info", "debug", "trace"] = "info"
    api_docs_enabled: bool = True
    cors_allowed_origins: list[str] = Field(default_factory=list)
    database_path: Path = PROJECT_ROOT / ".local" / "clear-context.db"
    model_catalog_path: Path = PROJECT_ROOT / "config" / "models.yaml"
    prompt_catalog_path: Path = PROJECT_ROOT / "config" / "prompts.yaml"
    extractor_catalog_path: Path = PROJECT_ROOT / "config" / "extractors.yaml"
    prompt_claim_extraction: str = Field(default="v2", min_length=1)
    extraction_response_capacity: int = Field(default=24, ge=1, le=64)
    extraction_chunk_characters: int = Field(default=600, ge=400, le=8000)
    extraction_min_chunk_characters: int = Field(default=200, ge=80, le=400)
    extraction_context_characters: int = Field(default=600, ge=0, le=2000)
    extraction_max_calls: int = Field(default=24, ge=1, le=100)
    extraction_max_output_tokens: int = Field(default=32768, ge=128, le=131072)
    extraction_max_seconds: float = Field(default=120, ge=1, le=600)
    model_default: str = ""
    model_claim_extraction: str = ""
    model_screenshot: str = ""
    model_research: str = ""
    model_judge: str = ""
    model_report: str = ""
    model_allow_training_use: bool = False
    meta_api_key: SecretStr = Field(default=SecretStr(""), exclude=True)

    @field_validator("cors_allowed_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        normalized = []
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or "*" in parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths.")
            _ = parsed.port
            normalized.append(origin.rstrip("/"))
        return list(dict.fromkeys(normalized))


class CatalogModel(BaseModel):
    name: str
    api_model_id: str | None
    access: str
    training_use: bool = False


class CatalogDefaults(BaseModel):
    model: str


class ModelCatalog(BaseModel):
    schema_version: Literal[1]
    defaults: CatalogDefaults
    models: dict[str, CatalogModel]


class ModelSelection(BaseModel):
    alias: str
    api_model_id: str
    training_use: bool


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_model_selections(settings: Settings) -> dict[str, ModelSelection]:
    with resolve_path(settings.model_catalog_path).open(encoding="utf-8-sig") as stream:
        catalog = ModelCatalog.model_validate(yaml.safe_load(stream))
    selections = {}
    for task in TASKS:
        override = getattr(settings, f"model_{task}").strip()
        alias = override or settings.model_default.strip() or catalog.defaults.model
        model = catalog.models.get(alias)
        if model is None:
            raise ValueError(f"Unknown model alias for {task}.")
        if model.access not in {"meta_api", "meta_api_select_countries"}:
            raise ValueError(f"Model for {task} requires an unsupported access method.")
        if model.api_model_id not in TEXT_MODELS:
            raise ValueError(f"Model for {task} must support text-output investigations.")
        if model.training_use and not settings.model_allow_training_use:
            raise ValueError(f"Contributor model for {task} requires training-use opt-in.")
        selections[task] = ModelSelection(
            alias=alias, api_model_id=model.api_model_id, training_use=model.training_use
        )
    return selections
