from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.draft import Draft
    from app.db.models.verification import Verification


class Claim(Base):
    """
    Individual marketing claim parsed or extracted from a Draft.
    Tracks exact character positions (start_char, end_char) within the draft content.
    """
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    draft_id: Mapped[int] = mapped_column(
        ForeignKey("drafts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_claims_draft_type", "draft_id", "claim_type"),
    )

    # Relationships
    draft: Mapped["Draft"] = relationship("Draft", back_populates="claims")
    verifications: Mapped[List["Verification"]] = relationship(
        "Verification",
        back_populates="claim",
        cascade="all, delete-orphan",
    )

