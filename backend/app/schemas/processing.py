"""
processing.py — Pydantic response schemas for the document processing pipeline.

These models define the JSON shapes returned by:
  - POST /api/documents/{document_id}/process
  - GET  /api/documents/{document_id}/chunks
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ProcessingResponse(BaseModel):
    """Returned by POST /api/documents/{document_id}/process."""

    document_id: str = Field(..., description="String document identifier.")
    business_id: str = Field(..., description="String business identifier.")
    processing_status: str = Field(
        ...,
        description="'processed' on first run, 'already_processed' if idempotent.",
    )
    chunk_count: int = Field(..., description="Number of text chunks created.")
    embedding_count: int = Field(..., description="Number of embedding vectors stored.")
    embedding_model: str = Field(..., description="HuggingFace model name used.")
    embedding_dimension: int = Field(..., description="Vector dimensionality (384).")
    processing_duration_ms: float = Field(
        ..., description="Wall-clock time for the processing call in milliseconds."
    )


class ChunkItem(BaseModel):
    """Metadata summary for a single DocumentChunk row."""

    chunk_id: int = Field(..., description="Primary key of the document_chunks row.")
    chunk_index: int = Field(..., description="Zero-based sequential position in the document.")
    char_count: int = Field(..., description="Length of the chunk text in characters.")
    start_char: int = Field(..., description="Inclusive character offset in the source document.")
    end_char: int = Field(..., description="Exclusive character offset in the source document.")
    has_embedding: bool = Field(..., description="True if an Embedding row exists for this chunk.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunking configuration metadata.")


class ChunksListResponse(BaseModel):
    """Returned by GET /api/documents/{document_id}/chunks."""

    document_id: str = Field(..., description="String document identifier.")
    total_chunks: int = Field(..., description="Total number of chunks for this document.")
    items: List[ChunkItem] = Field(..., description="Ordered list of chunk metadata items.")

