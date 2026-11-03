from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, Float, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.claim import Claim
    from app.db.models.chunk import DocumentChunk


class Verification(Base):
    """
    Automated verification result produced by the RAG verification engine.
    Contains the predicted verdict, rationale, and optional confidence score.
    """
    __tablename__ = "verifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    claim_id: Mapped[int] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    verdict: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_verifications_claim_created", "claim_id", "created_at"),
    )

    # Relationships
    claim: Mapped["Claim"] = relationship("Claim", back_populates="verifications")
    evidence: Mapped[List["VerificationEvidence"]] = relationship(
        "VerificationEvidence",
        back_populates="verification",
        cascade="all, delete-orphan",
    )
    human_reviews: Mapped[List["HumanReview"]] = relationship(
        "HumanReview",
        back_populates="verification",
        cascade="all, delete-orphan",
    )


class VerificationEvidence(Base):
    """
    Grounding evidence citing specific DocumentChunks that justify the Verification verdict.
    """
    __tablename__ = "verification_evidence"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    verification_id: Mapped[int] = mapped_column(
        ForeignKey("verifications.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    relevance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    verification: Mapped["Verification"] = relationship("Verification", back_populates="evidence")
    chunk: Mapped[Optional["DocumentChunk"]] = relationship("DocumentChunk", back_populates="evidence_records")


class HumanReview(Base):
    """
    Audit and human-in-the-loop review record for ambiguous or flagged verifications.
    """
    __tablename__ = "human_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    verification_id: Mapped[int] = mapped_column(
        ForeignKey("verifications.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    reviewer_decision: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    verification: Mapped["Verification"] = relationship("Verification", back_populates="human_reviews")
