"""
chunker.py — Recursive character text splitter for ClaimGuard document chunking.

Wraps LangChain's RecursiveCharacterTextSplitter to produce a list of chunk
dictionaries that carry the chunk content, character offsets, sequential index,
and a metadata dict containing the splitter configuration used.

Design principles:
- Configuration is read from settings so chunk_size / chunk_overlap are never
  hard-coded at call sites.
- Character offsets are computed by a linear scan of the original text so that
  evidence retrieval can always trace a chunk back to its exact source position.
- Rejects empty input early with DocumentExtractionError (HTTP 422).
"""

from __future__ import annotations

from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings
from app.ingestion.exceptions import DocumentExtractionError


def chunk_document(text: str) -> List[dict]:
    """
    Split *text* into overlapping chunks using RecursiveCharacterTextSplitter.

    Returns
    -------
    List[dict]
        Each dict has:
        - ``chunk_index``  : int  — zero-based sequential position
        - ``content``      : str  — the chunk text
        - ``start_char``   : int  — inclusive start offset in the original text
        - ``end_char``     : int  — exclusive end offset in the original text
        - ``metadata``     : dict — chunking configuration for provenance

    Raises
    ------
    DocumentExtractionError
        If *text* is empty or contains only whitespace.
    """
    if not text or not text.strip():
        raise DocumentExtractionError(
            "Cannot chunk document: extracted text is empty or contains only whitespace."
        )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )

    raw_chunks: List[str] = splitter.split_text(text)

    chunk_metadata = {
        "chunk_size": settings.CHUNK_SIZE,
        "chunk_overlap": settings.CHUNK_OVERLAP,
        "splitter": "RecursiveCharacterTextSplitter",
    }

    results: List[dict] = []
    search_start = 0  # walk forward so we never match an earlier occurrence

    for index, chunk_text in enumerate(raw_chunks):
        pos = text.find(chunk_text, search_start)
        if pos == -1:
            # Fallback: search from the beginning (shouldn't happen in practice)
            pos = text.find(chunk_text)

        start = pos
        end = pos + len(chunk_text)

        results.append(
            {
                "chunk_index": index,
                "content": chunk_text,
                "start_char": start,
                "end_char": end,
                "metadata": dict(chunk_metadata),  # each chunk gets its own copy
            }
        )

        # Advance search cursor past the start of this chunk (overlaps are OK)
        search_start = start + 1

    return results

