"""
hybrid.py — Hybrid retrieval engine combining dense vector search and BM25 sparse search with RRF.

Milestone 5 component for ClaimGuard:
1. Dense Retrieval: pgvector cosine distance using all-MiniLM-L6-v2 embeddings.
2. Sparse Retrieval: BM25Okapi over business-scoped document chunks.
3. Hybrid Fusion: Reciprocal Rank Fusion (RRF) with constant k=60.
4. Tenant Isolation: Every database query filters strictly by business_id.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.business import Business
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document
from app.db.models.embedding import Embedding
from app.ingestion.exceptions import BusinessNotFoundError
from app.retrieval.bm25 import search_bm25
from app.retrieval.embedder import generate_embeddings
from app.schemas.retrieval import EvidenceChunk, RetrievalResponse

# Standard Reciprocal Rank Fusion smoothing constant
RRF_K: int = 60
DEFAULT_CANDIDATE_LIMIT: int = 10


class HybridRetrievalService:
    """
    Coordinates dense vector retrieval, BM25 sparse retrieval, and Reciprocal Rank Fusion.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def search(
        self,
        business_id_str: str,
        query: str,
        top_k: int = 5,
        dense_limit: int = DEFAULT_CANDIDATE_LIMIT,
        sparse_limit: int = DEFAULT_CANDIDATE_LIMIT,
    ) -> RetrievalResponse:
        """
        Execute hybrid search for a query scoped to a single business tenant.

        Parameters
        ----------
        business_id_str : str
            The public business string identifier (e.g., 'biz_auraskin').
        query : str
            The marketing claim or text query to verify against approved documents.
        top_k : int, default 5
            Number of top fused results to return.
        dense_limit : int, default 10
            Number of candidates to fetch from dense vector search.
        sparse_limit : int, default 10
            Number of candidates to fetch from BM25 sparse search.

        Returns
        -------
        RetrievalResponse
            List of fused EvidenceChunk items ordered by descending RRF score.
        """
        clean_query = query.strip()
        if not clean_query:
            return RetrievalResponse(
                query=query,
                business_id=business_id_str,
                total_results=0,
                results=[],
            )

        # 1. Resolve business primary key
        biz_stmt = select(Business).where(Business.business_id == business_id_str)
        biz = self.db.execute(biz_stmt).scalar_one_or_none()
        if not biz:
            raise BusinessNotFoundError(business_id_str)

        # 2. Dense retrieval (pgvector cosine distance)
        dense_results = self._dense_search(
            business_pk=biz.id,
            query=clean_query,
            limit=dense_limit,
        )

        # 3. Sparse retrieval (BM25)
        sparse_results = self._sparse_search(
            business_pk=biz.id,
            query=clean_query,
            limit=sparse_limit,
        )

        # 4. Reciprocal Rank Fusion (RRF)
        fused_chunks = self._reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            top_k=top_k,
        )

        return RetrievalResponse(
            query=clean_query,
            business_id=business_id_str,
            total_results=len(fused_chunks),
            results=fused_chunks,
        )

    def _dense_search(
        self,
        business_pk: int,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Query pgvector for nearest chunks by cosine distance, filtered by business.
        """
        # Generate query vector (L2-normalized)
        query_vectors = generate_embeddings([query])
        query_vector = query_vectors[0]

        # Cosine distance operator in pgvector (<=>)
        stmt = (
            select(
                DocumentChunk.id.label("chunk_id"),
                Document.document_id.label("document_id"),
                Document.title.label("document_title"),
                Document.document_type.label("document_type"),
                DocumentChunk.content.label("content"),
                Embedding.embedding.cosine_distance(query_vector).label("distance"),
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .join(Embedding, Embedding.chunk_id == DocumentChunk.id)
            .where(
                Document.business_id == business_pk,
                Document.status == "active",
            )
            .order_by("distance")
            .limit(limit)
        )

        rows = self.db.execute(stmt).all()
        results: List[Dict[str, Any]] = []
        for rank, row in enumerate(rows, start=1):
            results.append({
                "chunk_id": row.chunk_id,
                "document_id": row.document_id,
                "document_title": row.document_title,
                "document_type": row.document_type,
                "content": row.content,
                "distance": float(row.distance) if row.distance is not None else 1.0,
                "dense_rank": rank,
            })
        return results

    def _sparse_search(
        self,
        business_pk: int,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Perform BM25 search over all active document chunks belonging to the business.
        """
        stmt = (
            select(
                DocumentChunk.id.label("chunk_id"),
                Document.document_id.label("document_id"),
                Document.title.label("document_title"),
                Document.document_type.label("document_type"),
                DocumentChunk.content.label("content"),
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                Document.business_id == business_pk,
                Document.status == "active",
            )
        )
        rows = self.db.execute(stmt).all()
        if not rows:
            return []

        candidates = [
            {
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "document_title": r.document_title,
                "document_type": r.document_type,
                "content": r.content,
            }
            for r in rows
        ]

        scored_candidates = search_bm25(query, candidates, text_key="content", top_k=limit)
        results: List[Dict[str, Any]] = []
        for doc_item, score, rank in scored_candidates:
            item = dict(doc_item)
            item["bm25_score"] = score
            item["bm25_rank"] = rank
            results.append(item)

        return results

    @staticmethod
    def _reciprocal_rank_fusion(
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        top_k: int = 5,
        k: int = RRF_K,
    ) -> List[EvidenceChunk]:
        """
        Merge ranked dense and sparse candidate lists using Reciprocal Rank Fusion.
        RRF_score(chunk) = sum(1 / (k + rank))
        """
        # Registry of chunk_id -> metadata & accumulator
        fused_map: Dict[int, Dict[str, Any]] = {}

        for item in dense_results:
            cid = item["chunk_id"]
            dense_rank = item["dense_rank"]
            score = 1.0 / (k + dense_rank)

            fused_map[cid] = {
                "chunk_id": cid,
                "document_id": item["document_id"],
                "document_title": item["document_title"],
                "document_type": item["document_type"],
                "content": item["content"],
                "dense_rank": dense_rank,
                "bm25_rank": None,
                "rrf_score": score,
            }

        for item in sparse_results:
            cid = item["chunk_id"]
            bm25_rank = item["bm25_rank"]
            score = 1.0 / (k + bm25_rank)

            if cid in fused_map:
                fused_map[cid]["bm25_rank"] = bm25_rank
                fused_map[cid]["rrf_score"] += score
            else:
                fused_map[cid] = {
                    "chunk_id": cid,
                    "document_id": item["document_id"],
                    "document_title": item["document_title"],
                    "document_type": item["document_type"],
                    "content": item["content"],
                    "dense_rank": None,
                    "bm25_rank": bm25_rank,
                    "rrf_score": score,
                }

        # Sort descending by rrf_score
        sorted_items = sorted(
            fused_map.values(),
            key=lambda x: x["rrf_score"],
            reverse=True,
        )

        evidence_list: List[EvidenceChunk] = []
        for item in sorted_items[:top_k]:
            evidence_list.append(
                EvidenceChunk(
                    chunk_id=item["chunk_id"],
                    document_id=item["document_id"],
                    document_title=item["document_title"],
                    document_type=item["document_type"],
                    content=item["content"],
                    dense_rank=item["dense_rank"],
                    bm25_rank=item["bm25_rank"],
                    rrf_score=round(item["rrf_score"], 6),
                )
            )

        return evidence_list

