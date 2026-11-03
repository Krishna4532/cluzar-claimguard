from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.business import Business
    from app.db.models.claim import Claim


class Draft(Base):
    """
    Candidate marketing copy submitted for automated claim extraction and verification.
    Scoped to a specific business tenant.
    """
    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_drafts_biz_status", "business_id", "status"),
    )

    # Relationships
    business: Mapped["Business"] = relationship("Business", back_populates="drafts")
    claims: Mapped[List["Claim"]] = relationship(
        "Claim",
        back_populates="draft",
        cascade="all, delete-orphan",
    )

