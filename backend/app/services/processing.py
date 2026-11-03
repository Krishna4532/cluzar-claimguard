"""
processing.py — Document processing service for ClaimGuard (Milestone 4).

Orchestrates the chunking + embedding pipeline for a single Document row:
  1. Resolve the document by its string document_id.
  2. Guard: reject superseded documents and empty content.
  3. Guard: if chunks already exist, return an "already_processed" summary
     (idempotent — safe to call multiple times).
  4. Chunk the document text via RecursiveCharacterTextSplitter.
  5. Embed all chunks in a single batched encode call.
  6. Persist DocumentChunk + Embedding rows in one atomic transaction.
  7. Return a ProcessingResult dataclass with key metrics.

All persistence happens inside a single ``db.begin()`` block; any failure
triggers a full rollback so no partial data is left in the database.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document
from app.db.models.embedding import Embedding
from app.ingestion.exceptions import (
    DocumentExtractionError,
    DocumentNotFoundError,
)
from app.retrieval.chunker import chunk_document
from app.retrieval.embedder import generate_embeddings


@dataclass
class ProcessingResult:
    """Carries the outcome metrics of a single document processing run."""
    document_id: str
    business_id: str
    processing_status: str  # "processed" | "already_processed"
    chunk_count: int
    embedding_count: int
    embedding_model: str
    embedding_dimension: int
    processing_duration_ms: float


class DocumentProcessingService:
    """
    Coordinates chunking and vector embedding for a single ingested Document.

    Parameters
    ----------
    db : Session
        An active SQLAlchemy session (injected via FastAPI ``Depends``).
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_document(self, document_id_str: str) -> ProcessingResult:
        """
        Chunk and embed *document_id_str*, persisting results to PostgreSQL.

        Returns a :class:`ProcessingResult`.  If the document has already been
        processed (chunks exist), returns immediately with
        ``processing_status="already_processed"`` without touching the database.

        Raises
        ------
        DocumentNotFoundError
            If no Document row matches *document_id_str*.
        DocumentExtractionError
            If the document has ``status="superseded"`` or empty content.
        """
        t_start = time.perf_counter()

        doc = self._resolve_document(document_id_str)
        business_id_str = self._get_business_id_str(doc)

        # Guard: superseded documents must not be re-processed
        if doc.status == "superseded":
            raise DocumentExtractionError(
                f"Document '{document_id_str}' has status 'superseded' and cannot be processed. "
                "Upload a new version first."
            )

        # Guard: empty content
        if not doc.content or not doc.content.strip():
            raise DocumentExtractionError(
                f"Document '{document_id_str}' has no extractable text content."
            )

        # Idempotency: if chunks already exist, return existing summary
        existing_chunk_count = self._count_existing_chunks(doc.id)
        if existing_chunk_count > 0:
            elapsed = (time.perf_counter() - t_start) * 1000
            return ProcessingResult(
                document_id=document_id_str,
                business_id=business_id_str,
                processing_status="already_processed",
                chunk_count=existing_chunk_count,
                embedding_count=existing_chunk_count,
                embedding_model=settings.EMBEDDING_MODEL_NAME,
                embedding_dimension=settings.EMBEDDING_DIMENSION,
                processing_duration_ms=round(elapsed, 2),
            )

        # Chunk + embed
        chunk_dicts = chunk_document(doc.content)
        texts = [c["content"] for c in chunk_dicts]
        vectors = generate_embeddings(texts)

        # Persist in a single atomic transaction
        self._persist(doc.id, chunk_dicts, vectors)

        elapsed = (time.perf_counter() - t_start) * 1000
        return ProcessingResult(
            document_id=document_id_str,
            business_id=business_id_str,
            processing_status="processed",
            chunk_count=len(chunk_dicts),
            embedding_count=len(vectors),
            embedding_model=settings.EMBEDDING_MODEL_NAME,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            processing_duration_ms=round(elapsed, 2),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_document(self, document_id_str: str) -> Document:
        """Fetch the Document ORM row or raise DocumentNotFoundError."""
        stmt = select(Document).where(Document.document_id == document_id_str)
        doc = self._db.execute(stmt).scalar_one_or_none()
        if doc is None:
            raise DocumentNotFoundError(document_id_str)
        return doc

    def _get_business_id_str(self, doc: Document) -> str:
        """Resolve the string business_id from the related Business row."""
        from app.db.models.business import Business
        stmt = select(Business.business_id).where(Business.id == doc.business_id)
        return self._db.execute(stmt).scalar_one()

    def _count_existing_chunks(self, doc_pk: int) -> int:
        """Return the number of DocumentChunk rows for *doc_pk*."""
        stmt = select(func.count(DocumentChunk.id)).where(
            DocumentChunk.document_id == doc_pk
        )
        return self._db.execute(stmt).scalar_one()

    def _persist(
        self,
        doc_pk: int,
        chunk_dicts: list[dict],
        vectors: list[list[float]],
    ) -> None:
        """
        Insert DocumentChunk and Embedding rows inside a single transaction.

        Uses ``flush()`` after the chunk inserts to obtain auto-generated
        primary keys before creating the Embedding rows.
        """
        db = self._db
        try:
            # 1. Create and insert chunk rows
            chunk_rows = [
                DocumentChunk(
                    document_id=doc_pk,
                    chunk_index=c["chunk_index"],
                    content=c["content"],
                    start_char=c["start_char"],
                    end_char=c["end_char"],
                    chunk_metadata=c["metadata"],
                )
                for c in chunk_dicts
            ]
            db.add_all(chunk_rows)
            db.flush()  # populate .id on each chunk_row

            # 2. Create embedding rows, referencing the freshly-flushed chunk IDs
            embedding_rows = [
                Embedding(
                    chunk_id=chunk_rows[i].id,
                    embedding=vectors[i],
                    embedding_model=settings.EMBEDDING_MODEL_NAME,
                )
                for i in range(len(chunk_rows))
            ]
            db.add_all(embedding_rows)
            db.commit()

        except Exception:
            db.rollback()
            raise

