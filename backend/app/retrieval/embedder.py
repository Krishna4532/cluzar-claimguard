"""
embedder.py — Sentence-Transformers embedding generator for ClaimGuard.

Uses ``sentence-transformers/all-MiniLM-L6-v2`` (384-dimensional dense vectors)
loaded once as a module-level singleton so that the heavy model is initialised
only on first use and then reused across all requests within the same process.

Design principles:
- Singleton via module-level ``_model`` variable + ``get_embedding_model()``.
- All embeddings are L2-normalised (cosine similarity ≡ dot product).
- Dimension and NaN/Inf validation after every encode call.
- Returns plain Python ``List[List[float]]`` — no NumPy leakage into callers.
"""

from __future__ import annotations

import math
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.ingestion.exceptions import DocumentExtractionError

# Module-level singleton — None until first call to get_embedding_model()
_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """
    Return the shared SentenceTransformer instance, loading it on first call.

    The model is cached in the module-level ``_model`` variable so that
    subsequent calls return the exact same object without re-initialisation.
    """
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    return _model


def _validate_vectors(vectors: np.ndarray) -> None:
    """
    Raise DocumentExtractionError if any vector contains NaN or Inf values,
    or if the embedding dimension does not match the expected value.

    Parameters
    ----------
    vectors : np.ndarray
        Shape ``(n, dim)`` array of float embeddings.
    """
    if vectors.ndim != 2 or vectors.shape[1] != settings.EMBEDDING_DIMENSION:
        raise DocumentExtractionError(
            f"Embedding dimension mismatch: expected {settings.EMBEDDING_DIMENSION}, "
            f"got {vectors.shape[1] if vectors.ndim == 2 else 'unknown'}."
        )

    if np.any(np.isnan(vectors)) or np.any(np.isinf(vectors)):
        raise DocumentExtractionError(
            "Generated embeddings contain NaN or Inf values — model output is invalid."
        )


def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Encode a list of text strings into L2-normalised dense vectors.

    Parameters
    ----------
    texts : List[str]
        Non-empty list of strings to embed.

    Returns
    -------
    List[List[float]]
        One 384-dimensional float list per input text, in the same order.

    Raises
    ------
    DocumentExtractionError
        If the input list is empty, or the resulting vectors are invalid
        (wrong dimension, NaN, or Inf).
    """
    if not texts:
        raise DocumentExtractionError("Cannot generate embeddings for an empty text list.")

    model = get_embedding_model()

    vectors: np.ndarray = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,  # L2 normalise → cosine sim == dot product
        show_progress_bar=False,
    )

    _validate_vectors(vectors)

    # Convert from numpy to plain Python lists for JSON-serialisability
    return vectors.tolist()

