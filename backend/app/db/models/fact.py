from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey, DateTime, Index, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.business import Business
    from app.db.models.document import Document

JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")


class StructuredFact(Base):
    """
    Extracted, highly-structured entity facts (e.g. approved product price, policy discount, validity date).
    Enables precise symbolic lookup and deterministic verification alongside vector similarity.
    """
    __tablename__ = "structured_facts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    fact_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    predicate: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    conditions: Mapped[Optional[dict]] = mapped_column(JSON_TYPE, nullable=True, default=dict)
    validity_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    validity_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_facts_biz_type_subj", "business_id", "fact_type", "subject"),
        Index("ix_facts_subj_predicate", "subject", "predicate"),
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="structured_facts")
    document: Mapped[Optional["Document"]] = relationship("Document", back_populates="structured_facts")

