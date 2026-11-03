"""
review.py — Pydantic schemas for the Human Review workflow (Milestone 7).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


ReviewDecisionType = Literal["approved", "rejected"]

ELIGIBLE_VERDICTS = {"needs_human", "unsupported"}


# ─────────────────────────────────────────────────────────────────────────────
# GET response models
# ─────────────────────────────────────────────────────────────────────────────

class ReviewEvidenceItem(BaseModel):
    """Evidence chunk cited for a verification."""
    evidence_id: int
    chunk_id: Optional[int] = None
    evidence_text: str
    relevance_score: Optional[float] = None


class ReviewClaimItem(BaseModel):
    """A single claim with its automated verdict and any existing human review."""
    claim_id: int
    claim_text: str
    claim_type: str
    start_char: int
    end_char: int
    verdict: str
    rationale: str
    confidence: Optional[float] = None
    evidence: List[ReviewEvidenceItem] = Field(default_factory=list)
    eligible_for_review: bool = Field(..., description="True if verdict is needs_human or unsupported.")
    human_decision: Optional[str] = Field(None, description="Existing reviewer decision, if any.")
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class VerificationReviewResponse(BaseModel):
    """Full review context for a single verification (GET)."""
    verification_id: int
    draft_id: int
    business_id: str
    draft_content: str
    draft_status: str
    total_claims: int
    pending_review_count: int = Field(..., description="Claims eligible for review but not yet reviewed.")
    claims: List[ReviewClaimItem]


# ─────────────────────────────────────────────────────────────────────────────
# POST request / response models
# ─────────────────────────────────────────────────────────────────────────────

class HumanReviewRequest(BaseModel):
    """Payload for POST /api/verifications/{verification_id}/review."""
    claim_id: Optional[int] = Field(None, description="Optional claim ID to validate against the verification.")
    decision: ReviewDecisionType = Field(..., description="Human reviewer decision: approved or rejected.")
    notes: Optional[str] = Field(None, max_length=2000, description="Optional reviewer notes.")


class HumanReviewResponse(BaseModel):
    """Response after persisting a human review decision."""
    review_id: int
    verification_id: int
    claim_id: int
    claim_text: str
    automated_verdict: str
    human_decision: str
    notes: Optional[str] = None
    created_at: datetime

