"""
retrieval.py — Pydantic schemas for the hybrid retrieval engine (Milestone 5).
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class RetrievalRequest(BaseModel):
    """Payload for POST /api/retrieval/search."""

    business_id: str = Field(..., description="Business identifier (e.g. 'biz_auraskin').")
    query: str = Field(..., min_length=1, description="Marketing claim or search query.")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of top fused results to return.")


class EvidenceChunk(BaseModel):
    """An authoritative document chunk retrieved and ranked by hybrid fusion."""

    chunk_id: int = Field(..., description="Primary key ID of the document chunk.")
    document_id: str = Field(..., description="Document business identifier (e.g. 'doc_as_01').")
    document_title: str = Field(..., description="Title of the parent document.")
    document_type: str = Field(..., description="Type/category of the document.")
    content: str = Field(..., description="Exact textual content of the chunk.")
    dense_rank: Optional[int] = Field(None, description="1-based rank in dense vector search, if retrieved.")
    bm25_rank: Optional[int] = Field(None, description="1-based rank in BM25 sparse search, if retrieved.")
    rrf_score: float = Field(..., description="Reciprocal Rank Fusion (RRF) score.")


class RetrievalResponse(BaseModel):
    """Response payload for POST /api/retrieval/search."""

    query: str = Field(..., description="Echoed input search query.")
    business_id: str = Field(..., description="Target business identifier.")
    total_results: int = Field(..., description="Total number of fused evidence chunks returned.")
    results: List[EvidenceChunk] = Field(..., description="Top ranked evidence chunks ordered by descending RRF score.")

