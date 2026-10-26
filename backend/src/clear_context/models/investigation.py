from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from clear_context.db.base import Base


class InvestigationRow(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)
    mode: Mapped[str] = mapped_column(String(20))
    revision: Mapped[int]
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(50))
    limitations: Mapped[list] = mapped_column(JSON, default=list)
