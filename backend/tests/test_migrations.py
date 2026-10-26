from alembic import command
from conftest import migration_config
from sqlalchemy import inspect, text

from clear_context.db.session import create_database


def test_migration_round_trip(tmp_path):
    database_path = tmp_path / "migration.db"
    config = migration_config(database_path)
    command.upgrade(config, "head")
    engine = create_database(database_path)
    try:
        expected = {
            "investigations",
            "claims",
            "sources",
            "evidence",
            "findings",
            "finding_evidence",
            "research_steps",
        }
        assert expected <= set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        command.check(config)
        command.downgrade(config, "base")
        assert not expected & set(inspect(engine).get_table_names())
        command.upgrade(config, "head")
        assert expected <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
