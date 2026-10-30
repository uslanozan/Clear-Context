from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from clear_context.api.router import router
from clear_context.core.prompts import load_claim_extraction_prompt
from clear_context.core.settings import Settings, load_model_selections, resolve_path
from clear_context.db.session import create_database, create_session_factory
from clear_context.providers.fact_check import build_fact_check_search
from clear_context.providers.meta import MetaInvestigationProvider
from clear_context.providers.meta_media import MetaMediaAnalyzer, MockMediaAnalyzer
from clear_context.providers.mock import MockInvestigationProvider
from clear_context.providers.reverse_image import build_reverse_image_search
from clear_context.repositories.investigation import InvestigationRepository
from clear_context.services.investigation import InvestigationService
from clear_context.services.investigation_research import InvestigationResearch


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    selections = load_model_selections(settings)
    prompt = load_claim_extraction_prompt(settings)
    provider = (
        MetaInvestigationProvider(settings, selections["claim_extraction"], prompt=prompt)
        if settings.app_mode == "meta"
        else MockInvestigationProvider()
    )
    live = settings.app_mode == "meta" and settings.allow_paid_api_calls
    media_analyzer = (
        MetaMediaAnalyzer(
            settings, selections["screenshot"], resolve_path(settings.prompt_catalog_path)
        )
        if live
        else MockMediaAnalyzer()
    )
    # Preview mode makes no external calls, including reverse image search.
    reverse_image = build_reverse_image_search(settings) if live else None
    fact_checks = build_fact_check_search(settings) if live else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_database(resolve_path(settings.database_path))
        try:
            with engine.connect() as connection:
                try:
                    revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                except Exception:
                    raise RuntimeError(
                        "Database not initialized. Run Alembic upgrade head."
                    ) from None
                if revision != "0006":
                    raise RuntimeError("Database schema is unsupported. Run Alembic upgrade head.")
            repository = InvestigationRepository(create_session_factory(engine))
            repository.fail_interrupted()
            app.state.repository = repository
            research = None
            if settings.app_mode == "meta" and settings.research_enabled:
                research = InvestigationResearch(
                    settings,
                    selections,
                    resolve_path(settings.database_path).parent / "research.sqlite",
                )
            app.state.service = InvestigationService(
                repository,
                provider,
                settings.graph_recursion_limit,
                research,
                media_analyzer=media_analyzer,
                reverse_image=reverse_image,
                media_dir=resolve_path(settings.media_dir),
                fact_checks=fact_checks,
            )
            app.state.media_dir = resolve_path(settings.media_dir)
            app.state.models = selections
            yield
        finally:
            engine.dispose()
            if reverse_image is not None:
                reverse_image.close()
            if fact_checks is not None:
                fact_checks.close()

    app = FastAPI(
        title="Clear Context API",
        version="0.1.0",
        lifespan=lifespan,
        description="Local investigation API with optional bounded text research.",
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
    app.state.mode = settings.app_mode
    app.state.research_enabled = settings.app_mode == "meta" and settings.research_enabled
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
            expose_headers=["Location"],
            allow_credentials=False,
        )
    app.include_router(router)
    return app
