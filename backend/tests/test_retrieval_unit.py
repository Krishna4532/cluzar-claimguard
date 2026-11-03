"""
test_retrieval_unit.py — In-memory unit tests for BM25 and Reciprocal Rank Fusion (Milestone 5).
No external database connections needed.
"""

from __future__ import annotations

import pytest
from app.retrieval.bm25 import tokenize, BM25Okapi, search_bm25
from app.retrieval.hybrid import HybridRetrievalService, RRF_K


class TestTokenizer:

    def test_basic_tokenization(self):
        text = "Vitamin C Serum helps with skin glow and radiance."
        tokens = tokenize(text)
        assert "vitamin" in tokens
        assert "c" in tokens
        assert "serum" in tokens
        assert "radiance" in tokens

    def test_preserves_currency_and_numbers(self):
        text = "UrbanNest Nordic Table is ₹24,999 with 15% discount or INR 21,249."
        tokens = tokenize(text)
        assert "₹24,999" in tokens
        assert "15%" in tokens
        assert "inr" in tokens
        assert "21,249" in tokens

    def test_preserves_hinglish_and_devanagari(self):
        text = "Yeh table bohot durable hai. AuraSkin ka glow serum ₹899 mein milta hai."
        tokens = tokenize(text)
        assert "durable" in tokens
        assert "auraskin" in tokens
        assert "₹899" in tokens

    def test_empty_string(self):
        assert tokenize("") == []
        assert tokenize("   ") == []


class TestBM25Okapi:

    def test_bm25_exact_match_ranking(self):
        corpus = [
            tokenize("AuraSkin Vitamin C Glow Serum with 15% Ethyl Ascorbic Acid."),
            tokenize("UrbanNest ErgoComfort Office Chair with adjustable lumbar support."),
            tokenize("AuraSkin HydraDew Hyaluronic Gel Moisturizer with SPF 30."),
        ]
        bm25 = BM25Okapi(corpus)
        query = tokenize("Vitamin C Serum")
        scores = bm25.get_scores(query)

        # Doc 0 should have the highest score
        assert scores[0] > scores[1]
        assert scores[0] > scores[2]
        assert scores[1] == 0.0

    def test_bm25_empty_corpus(self):
        bm25 = BM25Okapi([])
        scores = bm25.get_scores(["test"])
        assert scores == []

    def test_search_bm25_helper(self):
        docs = [
            {"id": 1, "content": "AuraSkin Radiance Glow Vitamin C Serum costs INR 899."},
            {"id": 2, "content": "UrbanNest CloudRest Sofa in Ivory velvet fabric."},
            {"id": 3, "content": "AuraSkin Clarifying Face Toner with 2% Salicylic Acid."},
        ]
        results = search_bm25("INR 899 Serum", docs, text_key="content", top_k=2)
        assert len(results) == 1
        top_doc, score, rank = results[0]
        assert top_doc["id"] == 1
        assert rank == 1
        assert score > 0.0


class TestReciprocalRankFusion:

    def test_rrf_scoring_and_overlap_boosting(self):
        dense_results = [
            {"chunk_id": 101, "document_id": "doc_1", "document_title": "Doc A", "document_type": "specs", "content": "Serum A", "dense_rank": 1},
            {"chunk_id": 102, "document_id": "doc_2", "document_title": "Doc B", "document_type": "specs", "content": "Moisturizer B", "dense_rank": 2},
        ]
        sparse_results = [
            {"chunk_id": 102, "document_id": "doc_2", "document_title": "Doc B", "document_type": "specs", "content": "Moisturizer B", "bm25_rank": 1},
            {"chunk_id": 103, "document_id": "doc_3", "document_title": "Doc C", "document_type": "specs", "content": "Sunscreen C", "bm25_rank": 2},
        ]

        # Chunk 102 appears in both:
        # Dense rank 2 -> 1 / (60 + 2) = 1/62 ≈ 0.016129
        # BM25 rank 1  -> 1 / (60 + 1) = 1/61 ≈ 0.016393
        # Total for 102 ≈ 0.032522
        #
        # Chunk 101 only dense rank 1 -> 1 / (60 + 1) = 1/61 ≈ 0.016393
        # Chunk 103 only sparse rank 2 -> 1 / (60 + 2) = 1/62 ≈ 0.016129

        fused = HybridRetrievalService._reciprocal_rank_fusion(
            dense_results=dense_results,
            sparse_results=sparse_results,
            top_k=5,
            k=60,
        )

        assert len(fused) == 3
        # Chunk 102 must be ranked 1st because it appeared in both dense and sparse!
        assert fused[0].chunk_id == 102
        assert fused[0].dense_rank == 2
        assert fused[0].bm25_rank == 1
        expected_score_102 = round(1.0 / 62 + 1.0 / 61, 6)
        assert abs(fused[0].rrf_score - expected_score_102) < 1e-5

        # Chunk 101 should be 2nd
        assert fused[1].chunk_id == 101
        assert fused[1].dense_rank == 1
        assert fused[1].bm25_rank is None

        # Chunk 103 should be 3rd
        assert fused[2].chunk_id == 103
        assert fused[2].dense_rank is None
        assert fused[2].bm25_rank == 2

    def test_rrf_truncates_to_top_k(self):
        dense_results = [
            {"chunk_id": i, "document_id": f"doc_{i}", "document_title": f"Doc {i}", "document_type": "policy", "content": f"Text {i}", "dense_rank": i}
            for i in range(1, 10)
        ]
        fused = HybridRetrievalService._reciprocal_rank_fusion(dense_results, [], top_k=3)
        assert len(fused) == 3
        assert fused[0].chunk_id == 1
        assert fused[1].chunk_id == 2
        assert fused[2].chunk_id == 3

