from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.document import Document
    from app.db.models.fact import StructuredFact
    from app.db.models.draft import Draft


class Business(Base):
    """
    Business entity representing a tenant (e.g. AuraSkin, UrbanNest).
    Provides tenant isolation for documents, structured facts, and marketing drafts.
    """
    __tablename__ = "businesses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    business_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    industry: Mapped[str] = mapped_column(String(128), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    structured_facts: Mapped[List["StructuredFact"]] = relationship(
        "StructuredFact",
        back_populates="business",
        cascade="all, delete-orphan",
    )
    drafts: Mapped[List["Draft"]] = relationship(
        "Draft",
        back_populates="business",
        cascade="all, delete-orphan",
    )

