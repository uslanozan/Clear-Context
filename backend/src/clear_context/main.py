from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from clear_context.api.router import router
from clear_context.core.settings import Settings, load_model_selections, resolve_path
from clear_context.db.session import create_database, create_session_factory
from clear_context.providers.mock import MockInvestigationProvider
from clear_context.repositories.investigation import InvestigationRepository
from clear_context.services.investigation import InvestigationService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    selections = load_model_selections(settings)

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
                if revision != "0001":
                    raise RuntimeError("Database schema is unsupported. Run Alembic upgrade head.")
            repository = InvestigationRepository(create_session_factory(engine))
            repository.fail_interrupted()
            app.state.repository = repository
            app.state.service = InvestigationService(
                repository, MockInvestigationProvider(), settings.graph_recursion_limit
            )
            app.state.models = selections
            yield
        finally:
            engine.dispose()

    app = FastAPI(
        title="Clear Context API",
        version="0.1.0",
        lifespan=lifespan,
        description="Local development API. Mock mode only; no external research or model calls.",
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
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
