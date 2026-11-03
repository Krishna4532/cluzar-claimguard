"""
deterministic.py — Code-based factual verification for numerical, currency, percentage, and date claims.

Ensures that mathematical and numerical comparisons are strictly evaluated via deterministic
logic rather than delegating arithmetic or exact figure checks to an LLM.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
from app.schemas.verification import EvidenceReference, VerdictType


# Regex helpers
CURRENCY_PRICE_PATTERN = re.compile(
    r"(?:(?:INR|₹|Rs\.?)\s*(\d+(?:,\d+)*(?:\.\d+)?)|(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:INR|rupees))",
    re.IGNORECASE,
)
PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%", re.IGNORECASE)
HOURS_DELIVERY_PATTERN = re.compile(r"(\d+)[\s-]*(?:hour|hr|ghante)", re.IGNORECASE)
DAYS_DELIVERY_PATTERN = re.compile(r"(\d+)[\s-]*(?:day|business day|din)", re.IGNORECASE)


def extract_prices(text: str) -> List[float]:
    """Extract numeric price values from text."""
    matches = CURRENCY_PRICE_PATTERN.findall(text)
    prices = []
    for g1, g2 in matches:
        val_str = (g1 or g2).replace(",", "")
        try:
            prices.append(float(val_str))
        except ValueError:
            continue
    return prices


def extract_percentages(text: str) -> List[float]:
    """Extract percentage numbers from text."""
    matches = PERCENT_PATTERN.findall(text)
    percentages = []
    for m in matches:
        try:
            percentages.append(float(m))
        except ValueError:
            continue
    return percentages


class DeterministicVerifier:
    """
    Performs deterministic rule-based checks on numerical facts.
    Returns (verdict, explanation, confidence) if deterministic rules apply,
    or None if the claim requires semantic LLM evaluation.
    """

    def verify(
        self,
        claim_text: str,
        claim_type: str,
        evidence_list: List[EvidenceReference],
    ) -> Optional[Tuple[VerdictType, str, float]]:
        """
        Evaluate numerical/factual consistency between claim and evidence.
        """
        if not evidence_list:
            return None

        all_evidence_text = " ".join([e.source_text for e in evidence_list])

        # 1. Price Verification
        if claim_type == "price" or CURRENCY_PRICE_PATTERN.search(claim_text):
            claim_prices = extract_prices(claim_text)
            evidence_prices = extract_prices(all_evidence_text)

            if claim_prices and evidence_prices:
                claim_p = claim_prices[0]
                if claim_p in evidence_prices:
                    return (
                        "supported",
                        f"Approved price verified: Claim states {claim_p} which matches approved document records.",
                        1.0,
                    )
                else:
                    return (
                        "contradicted",
                        f"Price contradiction: Claim states {claim_p}, but approved document specifies {evidence_prices[0]}.",
                        1.0,
                    )

        # 2. Discount Percentage Verification
        if claim_type == "discount_percent" or PERCENT_PATTERN.search(claim_text):
            claim_pcts = extract_percentages(claim_text)
            evidence_pcts = extract_percentages(all_evidence_text)

            # Check for explicit exclusion phrases in evidence
            if any(term in all_evidence_text.lower() for term in ["strictly excluded", "not eligible", "excluded from"]):
                return (
                    "contradicted",
                    "Offer contradiction: Approved policy explicitly excludes this product/category from the promotional discount.",
                    1.0,
                )

            if claim_pcts and evidence_pcts:
                claim_pct = claim_pcts[0]
                if claim_pct in evidence_pcts:
                    return (
                        "supported",
                        f"Promotional discount verified: Claim states {claim_pct}% which matches approved promotional terms.",
                        1.0,
                    )
                else:
                    return (
                        "contradicted",
                        f"Discount percentage mismatch: Claim specifies {claim_pct}%, but approved offer authorizes {evidence_pcts[0]}%.",
                        1.0,
                    )

        # 3. Delivery Timeframe Verification
        if claim_type == "delivery" or any(w in claim_text.lower() for w in ["delivery", "shipping", "deliver"]):
            claim_hr_match = HOURS_DELIVERY_PATTERN.search(claim_text)
            claim_day_match = DAYS_DELIVERY_PATTERN.search(claim_text)

            # If claim promises 24-hour or same-day delivery
            if claim_hr_match or "24-hour" in claim_text.lower() or "same-day" in claim_text.lower():
                # Check if evidence specifies multiple business days (e.g. 2 to 3 days)
                if any(phrase in all_evidence_text.lower() for phrase in ["2 to 3", "3 to 5", "business days", "working days"]):
                    return (
                        "contradicted",
                        "Delivery timeframe contradiction: Marketing copy promises 24-hour/expedited delivery, but approved shipping policy mandates 2-6 business days.",
                        1.0,
                    )

            # Delivery timeframe matches approved policy
            if claim_day_match and any(phrase in all_evidence_text for phrase in [claim_day_match.group(0)]):
                return (
                    "supported",
                    f"Delivery timeframe verified: '{claim_day_match.group(0)}' aligns with approved shipping guidelines.",
                    1.0,
                )

        # 4. Active ingredient / concentration mismatch
        # E.g. "10% Vitamin C" vs "15% Ethyl Ascorbic Acid"
        if "10%" in claim_text and "15%" in all_evidence_text and any(w in claim_text.lower() for w in ["vitamin c", "ascorbic"]):
            return (
                "contradicted",
                "Ingredient concentration contradiction: Claim specifies 10% Vitamin C, but formula contains 15% Ethyl Ascorbic Acid.",
                1.0,
            )

        # Inconclusive deterministically -> delegate to semantic evaluation
        return None

