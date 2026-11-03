"""
test_verification_unit.py — In-memory unit tests for Claim Extraction, Deterministic
Verification, and Semantic Verification (Milestone 6).

No database, no network. Tests run entirely against in-memory logic.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.pipeline.extractor import ClaimExtractor
from app.pipeline.deterministic import (
    DeterministicVerifier,
    extract_prices,
    extract_percentages,
)
from app.pipeline.semantic import SemanticVerifier
from app.schemas.verification import EvidenceReference, ExtractedClaim


# ─────────────────────────────────────────────────────────────────────────────
# Claim Extraction Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestClaimExtraction:

    def test_extract_claims_from_draft(self):
        """Deterministic extractor pulls verifiable claims from a marketing draft."""
        draft = (
            "Get the ultimate radiant skin with AuraSkin Radiance Glow Vitamin C Serum! "
            "Formulated with 15% Ethyl Ascorbic Acid, our vegan serum is now available "
            "for just INR 899. Plus, enjoy guaranteed 24-hour delivery anywhere in India!"
        )
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(draft)
        assert len(claims) >= 2, f"Expected at least 2 claims, got {len(claims)}"
        # At least one price claim and one delivery claim
        types = [c.type for c in claims]
        assert any(t in ("price", "product_feature") for t in types)

    def test_original_text_preserved_in_extraction(self):
        """Each extracted claim text must be an exact substring of the draft."""
        draft = (
            "AuraSkin Clarifying Salicylic Acid Face Cleanser costs INR 549. "
            "It contains 2% Salicylic Acid and is dermatologist-tested."
        )
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(draft)
        for claim in claims:
            assert draft[claim.start_char:claim.end_char] == claim.text, (
                f"Offset mismatch for claim: '{claim.text}'"
            )

    def test_empty_draft_returns_no_claims(self):
        """An empty draft produces an empty claims list."""
        extractor = ClaimExtractor()
        assert extractor.extract_claims("") == []
        assert extractor.extract_claims("   ") == []

    def test_hinglish_claim_extraction(self):
        """Claims in Hinglish text are extracted without text corruption."""
        draft = (
            "Yeh AuraSkin ka best serum hai! "
            "Radiance Glow Serum sirf INR 899 mein available hai."
        )
        extractor = ClaimExtractor()
        claims = extractor.extract_claims(draft)
        assert len(claims) >= 1
        all_text = " ".join(c.text for c in claims)
        assert "INR 899" in all_text or "899" in all_text


# ─────────────────────────────────────────────────────────────────────────────
# Price & Percentage Extraction Helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestNumericalExtraction:

    def test_extract_inr_prices(self):
        """Extract INR prices in multiple formats."""
        assert extract_prices("INR 899") == [899.0]
        assert extract_prices("₹24,999") == [24999.0]
        assert extract_prices("Rs. 649") == [649.0]
        assert extract_prices("costs 45,999 INR") == [45999.0]

    def test_extract_percentages(self):
        """Extract percentage values."""
        assert extract_percentages("15% Ethyl Ascorbic Acid") == [15.0]
        assert extract_percentages("flat 20% discount") == [20.0]
        assert extract_percentages("No percentage here") == []


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic Verification Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDeterministicVerification:

    def _make_evidence(self, text: str) -> list[EvidenceReference]:
        return [EvidenceReference(source_text=text)]

    def test_price_match_supported(self):
        """Claim price INR 899 matches evidence price INR 899 → supported."""
        verifier = DeterministicVerifier()
        result = verifier.verify(
            claim_text="available for just INR 899",
            claim_type="price",
            evidence_list=self._make_evidence("Radiance Glow Vitamin C Serum: INR 899 (30ml)."),
        )
        assert result is not None
        verdict, explanation, confidence = result
        assert verdict == "supported"
        assert confidence == 1.0

    def test_price_mismatch_contradicted(self):
        """Claim price INR 799 vs evidence INR 899 → contradicted."""
        verifier = DeterministicVerifier()
        result = verifier.verify(
            claim_text="now available for only INR 799",
            claim_type="price",
            evidence_list=self._make_evidence("Radiance Glow Vitamin C Serum: INR 899 (30ml)."),
        )
        assert result is not None
        verdict, explanation, confidence = result
        assert verdict == "contradicted"

    def test_percentage_match_supported(self):
        """Claim 20% matches evidence 20% → supported."""
        verifier = DeterministicVerifier()
        result = verifier.verify(
            claim_text="flat 20% discount on all skincare",
            claim_type="discount_percent",
            evidence_list=self._make_evidence("Flat 20% discount on eligible AuraSkin products."),
        )
        assert result is not None
        verdict, _, _ = result
        assert verdict == "supported"

    def test_percentage_mismatch_contradicted(self):
        """Claim 30% vs evidence 20% → contradicted."""
        verifier = DeterministicVerifier()
        result = verifier.verify(
            claim_text="flat 30% discount on all skincare",
            claim_type="discount_percent",
            evidence_list=self._make_evidence("Flat 20% discount on eligible AuraSkin products."),
        )
        assert result is not None
        verdict, _, _ = result
        assert verdict == "contradicted"

    def test_product_exclusion_contradicted(self):
        """Evidence explicitly excludes a product → contradicted."""
        verifier = DeterministicVerifier()
        result = verifier.verify(
            claim_text="20% discount on Clarifying Face Cleanser",
            claim_type="discount_percent",
            evidence_list=self._make_evidence(
                "Clarifying Salicylic Acid Face Cleanser is strictly excluded from this offer."
            ),
        )
        assert result is not None
        verdict, _, _ = result
        assert verdict == "contradicted"

    def test_24_hour_delivery_contradicted(self):
        """Claim promises 24-hour delivery but evidence says 2-3 business days → contradicted."""
        verifier = DeterministicVerifier()
        result = verifier.verify(
            claim_text="guaranteed 24-hour delivery anywhere in India",
            claim_type="delivery",
            evidence_list=self._make_evidence(
                "Metro cities receive delivery within 2 to 3 business days. "
                "Non-metro locations take 4 to 6 business days."
            ),
        )
        assert result is not None
        verdict, _, _ = result
        assert verdict == "contradicted"

    def test_no_evidence_returns_none(self):
        """No evidence → deterministic verifier cannot decide, returns None."""
        verifier = DeterministicVerifier()
        result = verifier.verify("Some claim", "other", [])
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Verification Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSemanticVerification:

    def _make_evidence(self, text: str) -> list[EvidenceReference]:
        return [EvidenceReference(source_text=text, document_id="doc_test_01")]

    def test_no_evidence_yields_unsupported(self):
        """Missing evidence must NEVER produce a supported verdict."""
        verifier = SemanticVerifier()
        verdict, explanation, confidence = verifier.verify(
            claim_text="Stock is limited, so shop today!",
            claim_type="other",
            evidence_list=[],
        )
        assert verdict == "unsupported"
        assert verdict != "supported"

    def test_offline_keyword_match_supported(self):
        """Offline verifier confirms claim when key terms appear in both claim and evidence."""
        verifier = SemanticVerifier()
        verdict, _, _ = verifier.verify(
            claim_text="Formulated with 15% Ethyl Ascorbic Acid",
            claim_type="product_feature",
            evidence_list=self._make_evidence(
                "Formulated with 15% Ethyl Ascorbic Acid, Ferulic Acid, and Hyaluronic Acid."
            ),
        )
        assert verdict == "supported"

    def test_offline_exclusion_contradicted(self):
        """Offline verifier detects 'strictly excluded' contradictions."""
        verifier = SemanticVerifier()
        verdict, _, _ = verifier.verify(
            claim_text="All products are eligible for warranty",
            claim_type="other",
            evidence_list=self._make_evidence(
                "Decorative items are strictly excluded from warranty coverage."
            ),
        )
        assert verdict == "contradicted"

    @patch("app.pipeline.semantic.settings")
    def test_malformed_llm_response_yields_needs_human(self, mock_settings):
        """If LLM returns an unrecognized verdict, result must be needs_human."""
        mock_settings.GROQ_API_KEY = "fake_key"
        mock_settings.OPENAI_API_KEY = None

        verifier = SemanticVerifier()

        # Mock the _verify_via_llm to simulate returning garbage verdict
        with patch.object(verifier, "_verify_via_llm", return_value=("needs_human", "LLM returned an unrecognized verdict 'maybe'. Flagged for human review.", 0.0)):
            verdict, explanation, conf = verifier.verify(
                claim_text="Test claim",
                claim_type="other",
                evidence_list=self._make_evidence("Test evidence"),
            )
        assert verdict == "needs_human"

    @patch("app.pipeline.semantic.settings")
    def test_llm_timeout_yields_needs_human(self, mock_settings):
        """LLM timeout must fail closed to needs_human, never supported."""
        import httpx
        mock_settings.GROQ_API_KEY = "fake_key"
        mock_settings.OPENAI_API_KEY = None

        verifier = SemanticVerifier()
        with patch.object(verifier, "_verify_via_llm", side_effect=httpx.TimeoutException("timeout")):
            verdict, explanation, conf = verifier.verify(
                claim_text="Test claim",
                claim_type="other",
                evidence_list=self._make_evidence("Test evidence"),
            )
        assert verdict == "needs_human"
        assert conf == 0.0

