from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, Index, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.business import Business
    from app.db.models.chunk import DocumentChunk
    from app.db.models.fact import StructuredFact

JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class Document(Base):
    """
    Authoritative business source document (e.g. price lists, specifications, policies).
    Supports content hashing, versioning, file_type tracking, page-level metadata,
    and status tracking for re-indexing workflows.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(16), default="txt", index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True, nullable=False)
    doc_metadata: Mapped[dict] = mapped_column("metadata", JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Composite index for tenant-scoped active document retrieval
    __table_args__ = (
        Index("ix_documents_biz_status", "business_id", "status"),
        Index("ix_documents_biz_type", "business_id", "document_type"),
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="documents")
    chunks: Mapped[List["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
    structured_facts: Mapped[List["StructuredFact"]] = relationship(
        "StructuredFact",
        back_populates="document",
        cascade="all, delete-orphan",
    )
