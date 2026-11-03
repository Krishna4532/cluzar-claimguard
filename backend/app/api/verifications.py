"""
verifications.py — API endpoints for automated claim verification (Milestone 6).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ingestion.exceptions import BusinessNotFoundError
from app.pipeline.verifier import VerificationPipeline
from app.schemas.verification import (
    VerificationCheckRequest,
    VerificationCheckResponse,
)

router = APIRouter(prefix="/api/verifications", tags=["Verifications"])


@router.post(
    "/check",
    response_model=VerificationCheckResponse,
    status_code=status.HTTP_200_OK,
    summary="Extract and verify factual claims in a marketing draft",
)
def check_draft_claims(
    payload: VerificationCheckRequest,
    db: Session = Depends(get_db),
):
    """
    Extract individual factual claims from a marketing draft and verify each claim
    against approved business source documents using hybrid retrieval, deterministic
    numerical checks, and fail-closed semantic verification.
    """
    clean_draft = payload.draft_text.strip()
    if not clean_draft:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Draft text must not be empty or whitespace only.",
        )

    pipeline = VerificationPipeline(db)
    try:
        response = pipeline.verify_draft(
            business_id_str=payload.business_id,
            draft_text=clean_draft,
        )
        return response
    except BusinessNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=err.message,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during draft verification: {str(err)}",
        )

