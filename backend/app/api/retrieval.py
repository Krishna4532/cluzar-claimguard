"""
retrieval.py — Hybrid retrieval endpoints for ClaimGuard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.ingestion.exceptions import BusinessNotFoundError
from app.retrieval.hybrid import HybridRetrievalService
from app.schemas.retrieval import RetrievalRequest, RetrievalResponse

router = APIRouter(prefix="/api/retrieval", tags=["Retrieval"])


@router.post(
    "/search",
    response_model=RetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid dense + BM25 retrieval of authoritative document chunks",
)
def hybrid_search(
    payload: RetrievalRequest,
    db: Session = Depends(get_db),
):
    """
    Retrieve authoritative evidence chunks for a marketing claim or query.
    Combines dense pgvector cosine distance and BM25 sparse search using RRF (k=60).
    Guarantees strict tenant isolation by scoping retrieval to business_id.
    """
    clean_query = payload.query.strip()
    if not clean_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Query must not be empty or whitespace only.",
        )

    service = HybridRetrievalService(db)
    try:
        response = service.search(
            business_id_str=payload.business_id,
            query=clean_query,
            top_k=payload.top_k,
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
            detail="An error occurred during hybrid retrieval.",
        )

