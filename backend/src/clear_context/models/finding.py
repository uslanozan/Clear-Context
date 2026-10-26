from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from clear_context.db.base import Base


class FindingRow(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), unique=True)
    assessment: Mapped[str] = mapped_column(String(20))
    explanation: Mapped[str] = mapped_column(Text)


class FindingEvidenceRow(Base):
    __tablename__ = "finding_evidence"

    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id"), primary_key=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), primary_key=True)
