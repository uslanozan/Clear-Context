from alembic import context

from clear_context.core.settings import Settings, resolve_path
from clear_context.db.session import create_database
from clear_context.models import Base

target_metadata = Base.metadata


def run_migrations():
    database_path = context.config.attributes.get("database_path")
    if database_path is None:
        database_path = resolve_path(Settings().database_path)
    engine = create_database(database_path)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported yet.")
run_migrations()
