# Build context: repository root (see compose.yaml).
FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Run from source so settings resolve config/ relative to /app.
    PYTHONPATH=/app/backend/src

WORKDIR /app

COPY backend/requirements-dev.lock backend/requirements-dev.lock
RUN pip install -r backend/requirements-dev.lock

COPY config config
COPY backend/alembic.ini backend/alembic.ini
COPY backend/migrations backend/migrations
COPY backend/src backend/src

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown app:app /data
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)"

# Migrations are idempotent; run them before every start so the volume stays current.
CMD ["sh", "-c", "python -m alembic -c backend/alembic.ini upgrade head && exec python -m clear_context"]
