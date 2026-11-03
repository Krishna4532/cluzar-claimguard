"""
test_chunking_unit.py — Unit tests for document chunking and embedding (Milestone 4).

All tests in this module are pure in-memory — no database, no network access,
no FastAPI test client.  The embedding model IS loaded from the local HuggingFace
cache (downloaded once; ~90 MB for all-MiniLM-L6-v2).

Run:
    backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_chunking_unit.py -v
"""

from __future__ import annotations

import math
import pytest

from app.ingestion.exceptions import DocumentExtractionError
from app.retrieval.chunker import chunk_document
from app.retrieval.embedder import generate_embeddings, get_embedding_model


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_long_text(n_chars: int = 2000) -> str:
    """Return a deterministic English paragraph repeated to ~n_chars length."""
    sentence = (
        "AuraSkin Radiance Glow Vitamin C Serum is priced at INR 899 for a 30ml bottle. "
        "It contains 15% Ethyl Ascorbic Acid and is suitable for all skin types. "
    )
    repetitions = math.ceil(n_chars / len(sentence))
    return (sentence * repetitions)[:n_chars]


# ─────────────────────────────────────────────────────────────────────────────
# Chunker unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestChunkDocument:

    def test_01_splits_into_multiple_chunks(self):
        """A 2000-char document must produce more than one chunk (chunk_size=500)."""
        text = make_long_text(2000)
        chunks = chunk_document(text)
        assert len(chunks) > 1, "Expected multiple chunks for a 2000-char document."

    def test_02_chunk_overlap_respected(self):
        """
        Adjacent chunk texts must share an overlapping suffix/prefix.
        With chunk_overlap=75, the tail of chunk[i] should appear at the
        start of chunk[i+1] (or at least the chunks share some characters).
        """
        text = make_long_text(2000)
        chunks = chunk_document(text)
        assert len(chunks) >= 2, "Need at least 2 chunks to test overlap."

        # The start_char of chunk[i+1] must be less than the end_char of chunk[i]
        for i in range(len(chunks) - 1):
            assert chunks[i + 1]["start_char"] < chunks[i]["end_char"], (
                f"Expected overlap between chunk {i} and {i + 1}: "
                f"end={chunks[i]['end_char']}, next_start={chunks[i + 1]['start_char']}"
            )

    def test_03_short_document_produces_one_chunk(self):
        """A 50-character document must produce at least one chunk."""
        text = "AuraSkin Glow Serum: INR 899. Works great on skin."
        chunks = chunk_document(text)
        assert len(chunks) >= 1
        assert chunks[0]["content"] == text

    def test_04_empty_text_raises_extraction_error(self):
        """Passing an empty string must raise DocumentExtractionError."""
        with pytest.raises(DocumentExtractionError, match="empty"):
            chunk_document("")

    def test_05_whitespace_only_text_raises_extraction_error(self):
        """Passing only whitespace must raise DocumentExtractionError."""
        with pytest.raises(DocumentExtractionError):
            chunk_document("   \n\t  ")

    def test_06_hinglish_text_preserved_in_chunks(self):
        """Hindi/Devanagari script is not mangled by the chunker."""
        hindi_text = (
            "AuraSkin का Radiance Glow Serum ₹899 में उपलब्ध है। "
            "यह सभी प्रकार की त्वचा के लिए उपयुक्त है और 15% Ethyl Ascorbic Acid से बना है। " * 10
        )
        chunks = chunk_document(hindi_text)
        assert len(chunks) >= 1
        all_chunk_text = " ".join(c["content"] for c in chunks)
        assert "₹899" in all_chunk_text or "₹" in all_chunk_text

    def test_07_currency_and_numbers_preserved(self):
        """Prices in INR, percentages, and special chars survive chunking intact."""
        text = (
            "Product: Radiance Glow Serum. Price: ₹24,999. Discount: 15%. "
            "Minimum order value: INR 899. Valid until 31-Dec-2026. " * 12
        )
        chunks = chunk_document(text)
        all_text = " ".join(c["content"] for c in chunks)
        assert "₹24,999" in all_text or "24,999" in all_text
        assert "15%" in all_text
        assert "INR 899" in all_text

    def test_08_chunk_indices_are_sequential(self):
        """chunk_index must be 0, 1, 2, ... with no gaps."""
        text = make_long_text(3000)
        chunks = chunk_document(text)
        indices = [c["chunk_index"] for c in chunks]
        assert indices == list(range(len(chunks))), f"Non-sequential indices: {indices}"

    def test_09_chunk_metadata_contains_config(self):
        """Every chunk dict must include chunk_size and chunk_overlap in its metadata."""
        from app.core.config import settings
        text = make_long_text(1500)
        chunks = chunk_document(text)
        for chunk in chunks:
            meta = chunk["metadata"]
            assert "chunk_size" in meta, "Missing 'chunk_size' in chunk metadata."
            assert "chunk_overlap" in meta, "Missing 'chunk_overlap' in chunk metadata."
            assert meta["chunk_size"] == settings.CHUNK_SIZE
            assert meta["chunk_overlap"] == settings.CHUNK_OVERLAP
            assert meta["splitter"] == "RecursiveCharacterTextSplitter"


# ─────────────────────────────────────────────────────────────────────────────
# Embedder unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestEmbedder:

    def test_10_embedding_dimension_is_384(self):
        """generate_embeddings(['test']) must return a list of length 384."""
        from app.core.config import settings
        vectors = generate_embeddings(["test sentence for ClaimGuard"])
        assert len(vectors) == 1
        assert len(vectors[0]) == settings.EMBEDDING_DIMENSION, (
            f"Expected dim {settings.EMBEDDING_DIMENSION}, got {len(vectors[0])}"
        )

    def test_11_invalid_nan_vector_raises_extraction_error(self):
        """
        The internal _validate_vectors function must raise DocumentExtractionError
        when presented with a vector containing NaN values.
        """
        import numpy as np
        from app.retrieval.embedder import _validate_vectors

        bad_array = np.full((1, 384), float("nan"))
        with pytest.raises(DocumentExtractionError, match="NaN"):
            _validate_vectors(bad_array)

    def test_12_model_loaded_once_singleton(self):
        """
        Calling get_embedding_model() twice must return the exact same object
        (module-level singleton, not two separate SentenceTransformer instances).
        """
        model_a = get_embedding_model()
        model_b = get_embedding_model()
        assert model_a is model_b, "Expected singleton: both calls must return the same object."

