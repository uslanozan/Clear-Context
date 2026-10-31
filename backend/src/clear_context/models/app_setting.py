from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from clear_context.db.base import Base


class AppSettingRow(Base):
    """A value set in the settings panel; it overrides the same setting from .env."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    # API keys are stored as plain text, like .env; the database stays on the local volume.
    value: Mapped[object] = mapped_column(JSON)
    updated_at: Mapped[str] = mapped_column(String(40))
