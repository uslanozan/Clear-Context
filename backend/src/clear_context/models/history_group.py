from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from clear_context.db.base import Base


class HistoryGroupRow(Base):
    """A named folder in the history list. It only organizes; it never changes a report."""

    __tablename__ = "history_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    position: Mapped[int]
    created_at: Mapped[str] = mapped_column(String(40))
