from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.db.base import Base
from app.core.config import settings

if TYPE_CHECKING:
    from app.db.models.chunk import DocumentChunk

VECTOR_TYPE = Vector(settings.EMBEDDING_DIMENSION).with_variant(JSON(), "sqlite")


class Embedding(Base):
    """
    Dense semantic vector representation of a DocumentChunk.
    Uses pgvector's Vector type sized to the exact embedding model dimension (384 for all-MiniLM-L6-v2).
    """
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chunk_id: Mapped[int] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    embedding = mapped_column(VECTOR_TYPE, nullable=False)
    embedding_model: Mapped[str] = mapped_column(
        String(128),
        default=settings.EMBEDDING_MODEL_NAME,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship
    chunk: Mapped["DocumentChunk"] = relationship("DocumentChunk", back_populates="embeddings")

