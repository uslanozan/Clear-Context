from alembic import command
from conftest import migration_config
from sqlalchemy import text

from clear_context.db.session import create_database


def test_usage_migration_preserves_existing_investigations(tmp_path):
    path = tmp_path / "legacy.db"
    config = migration_config(path)
    command.upgrade(config, "0001")
    engine = create_database(path)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO investigations "
                    "(id, text, status, mode, revision, created_at, updated_at, limitations) "
                    "VALUES ('legacy', 'Existing input', 'completed', 'mock', 1, 't', 't', '[]')"
                )
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT text, mode, model_usage FROM investigations WHERE id='legacy'")
            ).one()
            assert tuple(row) == ("Existing input", "mock", "[]")
    finally:
        engine.dispose()
