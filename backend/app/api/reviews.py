"""
reviews.py — Human Review API endpoints (Milestone 7).

GET  /api/verifications/{verification_id}/review  — Fetch review context
POST /api/verifications/{verification_id}/review  — Submit a human decision
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.business import Business
from app.db.models.claim import Claim
from app.db.models.draft import Draft
from app.db.models.verification import HumanReview, Verification, VerificationEvidence
from app.db.session import get_db
from app.schemas.review import (
    ELIGIBLE_VERDICTS,
    HumanReviewRequest,
    HumanReviewResponse,
    ReviewClaimItem,
    ReviewEvidenceItem,
    VerificationReviewResponse,
)

router = APIRouter(prefix="/api/verifications", tags=["Human Review"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_verification(verification_id: int, db: Session):
    """
    Load a Verification row and walk the FK chain back to Business.
    Returns (verification, claim, draft, business) or raises 404.
    """
    stmt = (
        select(Verification, Claim, Draft, Business.business_id)
        .join(Claim, Verification.claim_id == Claim.id)
        .join(Draft, Claim.draft_id == Draft.id)
        .join(Business, Draft.business_id == Business.id)
        .where(Verification.id == verification_id)
    )
    row = db.execute(stmt).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification {verification_id} not found.",
        )
    return row  # (Verification, Claim, Draft, business_id_str)


# ─────────────────────────────────────────────────────────────────────────────
# GET  — Review context
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{verification_id}/review",
    response_model=VerificationReviewResponse,
    summary="Fetch full review context for a verification",
)
def get_verification_review(
    verification_id: int,
    db: Session = Depends(get_db),
):
    """
    Return the draft, all claims, automated verdicts, evidence, and any
    existing human-review decisions for the verification's parent draft.
    """
    verif, claim, draft, biz_id_str = _resolve_verification(verification_id, db)

    # Load ALL claims for this draft (not just the one linked to this verification)
    all_claims = db.execute(
        select(Claim).where(Claim.draft_id == draft.id).order_by(Claim.id)
    ).scalars().all()

    claim_items = []
    pending_count = 0

    for c in all_claims:
        # Latest verification for this claim
        v = db.execute(
            select(Verification)
            .where(Verification.claim_id == c.id)
            .order_by(Verification.created_at.desc())
        ).scalars().first()

        if not v:
            continue

        # Evidence
        ev_rows = db.execute(
            select(VerificationEvidence).where(VerificationEvidence.verification_id == v.id)
        ).scalars().all()

        evidence_items = [
            ReviewEvidenceItem(
                evidence_id=e.id,
                chunk_id=e.chunk_id,
                evidence_text=e.evidence_text,
                relevance_score=e.relevance_score,
            )
            for e in ev_rows
        ]

        # Existing human review (latest)
        hr = db.execute(
            select(HumanReview)
            .where(HumanReview.verification_id == v.id)
            .order_by(HumanReview.created_at.desc())
        ).scalars().first()

        eligible = v.verdict in ELIGIBLE_VERDICTS
        if eligible and not hr:
            pending_count += 1

        claim_items.append(
            ReviewClaimItem(
                claim_id=c.id,
                claim_text=c.claim_text,
                claim_type=c.claim_type,
                start_char=c.start_char,
                end_char=c.end_char,
                verdict=v.verdict,
                rationale=v.rationale,
                confidence=v.confidence,
                evidence=evidence_items,
                eligible_for_review=eligible,
                human_decision=hr.reviewer_decision if hr else None,
                reviewer_notes=hr.reviewer_notes if hr else None,
                reviewed_at=hr.created_at if hr else None,
            )
        )

    return VerificationReviewResponse(
        verification_id=verification_id,
        draft_id=draft.id,
        business_id=biz_id_str,
        draft_content=draft.content,
        draft_status=draft.status,
        total_claims=len(claim_items),
        pending_review_count=pending_count,
        claims=claim_items,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST — Submit human decision
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/{verification_id}/review",
    response_model=HumanReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a human review decision for a verification",
)
def submit_human_review(
    verification_id: int,
    payload: HumanReviewRequest,
    db: Session = Depends(get_db),
):
    """
    Persist a human reviewer's decision (approved / rejected) for a specific
    verification.  Only claims with verdict ``needs_human`` or ``unsupported``
    are eligible.  Duplicate submissions are rejected with 409.
    """
    verif, claim, draft, biz_id_str = _resolve_verification(verification_id, db)

    # Guard: if claim_id is provided, verify it belongs to this verification
    if payload.claim_id is not None and payload.claim_id != claim.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Claim ID {payload.claim_id} does not match verification's claim ID {claim.id}.",
        )

    # Guard: only eligible verdicts
    if verif.verdict not in ELIGIBLE_VERDICTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Claim verdict is '{verif.verdict}'. "
                f"Only claims with verdict {sorted(ELIGIBLE_VERDICTS)} are eligible for human review."
            ),
        )

    # Guard: duplicate submission
    existing = db.execute(
        select(HumanReview).where(HumanReview.verification_id == verification_id)
    ).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"A human review already exists for verification {verification_id} "
                f"(decision: '{existing.reviewer_decision}'). Duplicate submissions are not allowed."
            ),
        )

    # Persist
    try:
        review = HumanReview(
            verification_id=verification_id,
            reviewer_decision=payload.decision,
            reviewer_notes=payload.notes,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
    except Exception:
        db.rollback()
        raise

    return HumanReviewResponse(
        review_id=review.id,
        verification_id=verification_id,
        claim_id=claim.id,
        claim_text=claim.claim_text,
        automated_verdict=verif.verdict,
        human_decision=review.reviewer_decision,
        notes=review.reviewer_notes,
        created_at=review.created_at,
    )

