"""
test_review_unit.py — Unit tests for Milestone 7 Human Review Workflow schemas and logic.
"""

import pytest
from pydantic import ValidationError

from app.schemas.review import (
    ELIGIBLE_VERDICTS,
    HumanReviewRequest,
    HumanReviewResponse,
    ReviewClaimItem,
    ReviewEvidenceItem,
    VerificationReviewResponse,
)


def test_eligible_verdicts_definition():
    """Verify eligible verdicts are strictly needs_human and unsupported."""
    assert ELIGIBLE_VERDICTS == {"needs_human", "unsupported"}
    assert "supported" not in ELIGIBLE_VERDICTS
    assert "contradicted" not in ELIGIBLE_VERDICTS


def test_human_review_request_valid():
    """Verify valid human review request payloads."""
    req_approved = HumanReviewRequest(decision="approved", notes="Verified by legal")
    assert req_approved.decision == "approved"
    assert req_approved.notes == "Verified by legal"
    assert req_approved.claim_id is None

    req_rejected = HumanReviewRequest(claim_id=42, decision="rejected", notes="Incorrect claim")
    assert req_rejected.claim_id == 42
    assert req_rejected.decision == "rejected"


def test_human_review_request_invalid_decision():
    """Verify invalid decision values are rejected by pydantic."""
    with pytest.raises(ValidationError):
        HumanReviewRequest(decision="pending")

    with pytest.raises(ValidationError):
        HumanReviewRequest(decision="maybe")

    with pytest.raises(ValidationError):
        HumanReviewRequest(decision="")


def test_human_review_request_notes_max_length():
    """Verify notes length limit is enforced."""
    long_notes = "a" * 2001
    with pytest.raises(ValidationError):
        HumanReviewRequest(decision="approved", notes=long_notes)


def test_review_claim_item_schema():
    """Verify ReviewClaimItem correctly reflects eligibility and reviewer decisions."""
    evidence = ReviewEvidenceItem(
        evidence_id=1,
        chunk_id=10,
        evidence_text="Return policy allows 30 days.",
        relevance_score=0.88,
    )
    claim_item = ReviewClaimItem(
        claim_id=5,
        claim_text="Return within 30 days.",
        claim_type="return_policy",
        start_char=0,
        end_char=22,
        verdict="needs_human",
        rationale="Borderline policy match",
        confidence=0.6,
        evidence=[evidence],
        eligible_for_review=True,
        human_decision="approved",
        reviewer_notes="Confirmed with manager",
    )
    assert claim_item.claim_id == 5
    assert claim_item.eligible_for_review is True
    assert claim_item.human_decision == "approved"
    assert len(claim_item.evidence) == 1
    assert claim_item.evidence[0].evidence_text == "Return policy allows 30 days."


def test_verification_review_response_schema():
    """Verify top-level VerificationReviewResponse schema."""
    resp = VerificationReviewResponse(
        verification_id=100,
        draft_id=10,
        business_id="biz_glow",
        draft_content="Sample draft content",
        draft_status="needs_human",
        total_claims=1,
        pending_review_count=1,
        claims=[
            ReviewClaimItem(
                claim_id=5,
                claim_text="Sample claim",
                claim_type="statement",
                start_char=0,
                end_char=12,
                verdict="needs_human",
                rationale="Uncertain",
                confidence=0.5,
                eligible_for_review=True,
            )
        ],
    )
    assert resp.verification_id == 100
    assert resp.pending_review_count == 1
    assert len(resp.claims) == 1

