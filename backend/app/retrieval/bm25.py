"""
bm25.py — Transparent, lightweight BM25Okapi implementation for ClaimGuard.

Supports exact keyword, numeric, currency (e.g. ₹24,999, INR 899), and
multilingual/Hinglish tokenization without external Java/Lucene dependencies.
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Sequence, Tuple


# Regex tokenizes words, numbers, and currency-prefixed expressions (e.g., ₹24,999, 15%, INR)
TOKEN_PATTERN = re.compile(r"(?:[₹$€£]?\d+(?:[.,]\d+)*%?|\w+)", re.UNICODE)


def tokenize(text: str) -> List[str]:
    """
    Tokenize text into lowercase terms, preserving currency symbols,
    percentages, decimal numbers, and non-ASCII (Hindi/Hinglish) characters.
    """
    if not text:
        return []
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


class BM25Okapi:
    """
    BM25Okapi ranking algorithm for sparse text retrieval.

    Parameters
    ----------
    corpus : Sequence[Sequence[str]]
        A list of tokenized documents.
    k1 : float, default 1.5
        Term frequency saturation parameter.
    b : float, default 0.75
        Document length normalization parameter.
    """

    def __init__(
        self,
        corpus: Sequence[Sequence[str]],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.doc_lengths: List[int] = [len(doc) for doc in corpus]
        self.avgdl = (
            sum(self.doc_lengths) / self.corpus_size if self.corpus_size > 0 else 0.0
        )
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}

        self._initialize(corpus)

    def _initialize(self, corpus: Sequence[Sequence[str]]) -> None:
        """Precompute term document frequencies and Robertson-Spärck Jones IDF."""
        df: Dict[str, int] = {}
        for doc in corpus:
            term_freq: Dict[str, int] = {}
            for term in doc:
                term_freq[term] = term_freq.get(term, 0) + 1
            self.doc_freqs.append(term_freq)

            for term in term_freq:
                df[term] = df.get(term, 0) + 1

        for term, freq in df.items():
            # Standard Okapi IDF with floor smoothing to prevent negative weights
            idf_score = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            self.idf[term] = max(idf_score, 0.0)

    def get_scores(self, query_tokens: Sequence[str]) -> List[float]:
        """
        Compute BM25 relevance scores for all documents in the corpus given query tokens.
        """
        scores = [0.0] * self.corpus_size
        if self.corpus_size == 0 or self.avgdl == 0.0:
            return scores

        for term in query_tokens:
            if term not in self.idf:
                continue
            term_idf = self.idf[term]

            for doc_idx, term_freq in enumerate(self.doc_freqs):
                tf = term_freq.get(term, 0)
                if tf == 0:
                    continue
                doc_len = self.doc_lengths[doc_idx]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                scores[doc_idx] += term_idf * (numerator / denominator)

        return scores


def search_bm25(
    query: str,
    documents: Sequence[Dict[str, Any]],
    text_key: str = "content",
    top_k: int = 10,
) -> List[Tuple[Dict[str, Any], float, int]]:
    """
    Search a collection of document dicts using BM25.

    Returns
    -------
    List[Tuple[Dict[str, Any], float, int]]
        List of (doc_dict, bm25_score, rank_1_based), ordered by descending score.
        Only items with score > 0 are returned.
    """
    if not query or not documents:
        return []

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    tokenized_corpus = [tokenize(doc.get(text_key, "")) for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)
    scores = bm25.get_scores(query_tokens)

    # Pair with indices
    scored_docs = [
        (documents[idx], score)
        for idx, score in enumerate(scores)
        if score > 0.0
    ]
    # Sort descending by score
    scored_docs.sort(key=lambda x: x[1], reverse=True)

    results: List[Tuple[Dict[str, Any], float, int]] = []
    for rank, (doc, score) in enumerate(scored_docs[:top_k], start=1):
        results.append((doc, score, rank))

    return results

