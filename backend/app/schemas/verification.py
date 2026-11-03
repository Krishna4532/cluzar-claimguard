"""
verification.py — Pydantic schemas for Claim Extraction and Verification (Milestone 6).
"""

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


VerdictType = Literal["supported", "contradicted", "unsupported", "needs_human"]
OverallStatusType = Literal["approved", "rejected", "flagged"]


class ExtractedClaim(BaseModel):
    """An individual factual claim extracted from marketing draft copy."""

    text: str = Field(..., min_length=1, description="Exact text of the claim as extracted from the draft.")
    type: str = Field(..., description="Category of claim: price, discount_percent, date, delivery, product_feature, other.")
    start_char: int = Field(..., ge=0, description="Inclusive start character offset in original draft.")
    end_char: int = Field(..., ge=0, description="Exclusive end character offset in original draft.")


class EvidenceReference(BaseModel):
    """Authoritative document chunk cited as justification for a verdict."""

    chunk_id: Optional[int] = Field(None, description="Database ID of the DocumentChunk.")
    document_id: Optional[str] = Field(None, description="Public document ID (e.g. 'doc_as_01').")
    document_title: Optional[str] = Field(None, description="Title of the source document.")
    source_text: str = Field(..., description="Exact chunk text used as grounding evidence.")
    relevance_score: Optional[float] = Field(None, description="Retrieval similarity or RRF score.")


class ClaimVerificationResult(BaseModel):
    """Complete verification outcome for an individual factual claim."""

    text: str = Field(..., description="Original claim text.")
    type: str = Field(..., description="Claim category.")
    start_char: int = Field(..., ge=0, description="Start offset in draft.")
    end_char: int = Field(..., ge=0, description="End offset in draft.")
    verdict: VerdictType = Field(..., description="One of: supported, contradicted, unsupported, needs_human.")
    explanation: str = Field(..., description="Clear explanation describing why the verdict was assigned.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0.")
    evidence: List[EvidenceReference] = Field(default_factory=list, description="Grounding evidence chunks.")


class VerificationCheckRequest(BaseModel):
    """Request payload for POST /api/verifications/check."""

    business_id: str = Field(..., description="Target business identifier (e.g. 'biz_auraskin').")
    draft_text: str = Field(..., min_length=1, description="Full candidate marketing copy text.")


class VerificationCheckResponse(BaseModel):
    """Response payload for POST /api/verifications/check."""

    draft_id: int = Field(..., description="Primary key ID of the persisted Draft record.")
    business_id: str = Field(..., description="Business identifier.")
    overall_status: OverallStatusType = Field(
        ...,
        description="Overall draft status: approved (all supported), rejected (any contradicted), or flagged (needs human review / unsupported).",
    )
    total_claims: int = Field(..., description="Total number of claims extracted.")
    supported_count: int = Field(..., description="Number of supported claims.")
    contradicted_count: int = Field(..., description="Number of contradicted claims.")
    unsupported_count: int = Field(..., description="Number of unsupported claims.")
    needs_human_count: int = Field(..., description="Number of claims requiring human review.")
    claims: List[ClaimVerificationResult] = Field(..., description="Per-claim verification results.")

