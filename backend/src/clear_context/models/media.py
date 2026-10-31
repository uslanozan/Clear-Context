from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from clear_context.db.base import Base


class MediaRow(Base):
    __tablename__ = "media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    mime_type: Mapped[str] = mapped_column(String(40))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    # Original file name for display only; files are stored by content hash.
    filename: Mapped[str] = mapped_column(Text)
    storage_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[str] = mapped_column(String(40))
    # Analysis and origin check, written when the report completes.
    finding: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # The linked page an image was taken from; null for uploads.
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class LinkRow(Base):
    __tablename__ = "links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    url: Mapped[str] = mapped_column(Text)
    finding: Mapped[dict] = mapped_column(JSON)
