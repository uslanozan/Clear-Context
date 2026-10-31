from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from clear_context.db.base import Base


class InvestigationRow(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)
    mode: Mapped[str] = mapped_column(String(20))
    research_mode: Mapped[str] = mapped_column(
        String(20), default="balanced", server_default="balanced"
    )
    revision: Mapped[int]
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(50))
    limitations: Mapped[list] = mapped_column(JSON, default=list)
    model_usage: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    extraction_coverage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analyzed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # A rerun or continuation points to the report it started from.
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    relation: Mapped[str | None] = mapped_column(String(20), nullable=True)
