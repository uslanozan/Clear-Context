from pathlib import Path

from alembic import command
from alembic.config import Config

from clear_context.core.settings import PROJECT_ROOT


def upgrade_database(database_path: Path) -> None:
    """Apply every pending migration to the database at this path; idempotent."""
    config = Config(str(PROJECT_ROOT / "backend" / "alembic.ini"))
    config.attributes["database_path"] = database_path
    command.upgrade(config, "head")
