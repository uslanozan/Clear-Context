from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from clear_context.db.base import Base


class ResearchStepRow(Base):
    __tablename__ = "research_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[str] = mapped_column(String(40))
