from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import Text, Integer, ForeignKey, DateTime, Index, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.document import Document
    from app.db.models.embedding import Embedding
    from app.db.models.verification import VerificationEvidence

JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class DocumentChunk(Base):
    """
    Granular text chunk derived from an authoritative Document.
    Tracks exact character offsets (start_char, end_char) to provide traceable gold evidence.
    """
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column("metadata", JSON_TYPE, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        Index("ix_chunks_doc_chunk_idx", "document_id", "chunk_index"),
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    embeddings: Mapped[List["Embedding"]] = relationship(
        "Embedding",
        back_populates="chunk",
        cascade="all, delete-orphan",
    )
    evidence_records: Mapped[List["VerificationEvidence"]] = relationship(
        "VerificationEvidence",
        back_populates="chunk",
    )

