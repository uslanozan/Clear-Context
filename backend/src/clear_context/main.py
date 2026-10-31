import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from clear_context.api.router import router
from clear_context.core.settings import Settings, resolve_path
from clear_context.db.session import create_database, create_session_factory
from clear_context.repositories.investigation import InvestigationRepository
from clear_context.repositories.settings import SettingsRepository
from clear_context.services.app_settings import differs_from_env, effective_settings, env_values
from clear_context.services.investigation import InvestigationService
from clear_context.services.runtime import build_runtime

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    research_workspace = resolve_path(settings.database_path).parent / "research.sqlite"
    # Fails early when .env cannot run; panel values are applied once the database opens.
    base_runtime = build_runtime(settings, research_workspace)
    env = env_values(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = create_database(resolve_path(settings.database_path))
        runtime = base_runtime
        try:
            with engine.connect() as connection:
                try:
                    revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                except Exception:
                    raise RuntimeError(
                        "Database not initialized. Run Alembic upgrade head."
                    ) from None
                if revision != "0009":
                    raise RuntimeError("Database schema is unsupported. Run Alembic upgrade head.")
            sessions = create_session_factory(engine)
            repository = InvestigationRepository(sessions)
            repository.fail_interrupted()
            app.state.repository = repository
            app.state.settings_repository = SettingsRepository(sessions)
            app.state.settings_error = None
            stored = app.state.settings_repository.load()
            # .env seeds panel fields that have no saved value yet; saved values are kept.
            # Empty keys are not stored, so a key added to .env later is seeded then.
            seed = {key: value for key, value in env.items() if key not in stored and value != ""}
            if seed:
                app.state.settings_repository.save(seed)
                stored |= seed
            if differs_from_env(stored, env):
                try:
                    runtime = build_runtime(
                        effective_settings(settings, stored), research_workspace
                    )
                    base_runtime.close()
                except ValueError as error:
                    # Keep the server usable with .env; the panel shows the problem.
                    logger.warning("Saved panel settings were not applied: %s", error)
                    app.state.settings_error = str(error)[:300]
            app.state.service = InvestigationService(
                repository,
                runtime,
                settings.graph_recursion_limit,
                media_dir=resolve_path(settings.media_dir),
            )
            app.state.media_dir = resolve_path(settings.media_dir)
            yield
        finally:
            engine.dispose()
            service = getattr(app.state, "service", None)
            (service.runtime if service else runtime).retire()

    app = FastAPI(
        title="Clear Context API",
        version="0.1.0",
        lifespan=lifespan,
        description="Local investigation API with optional bounded text research.",
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
    app.state.base_settings = settings
    app.state.env_values = env
    app.state.research_workspace = research_workspace
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_methods=["GET", "POST", "PUT"],
            allow_headers=["Content-Type"],
            expose_headers=["Location"],
            allow_credentials=False,
        )
    # Refuses other host names, so a rebound DNS name cannot reach the API from a web page.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.include_router(router)
    return app
