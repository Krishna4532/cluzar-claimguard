"""
extractor.py — Claim extraction engine supporting LLM with deterministic fallback (Milestone 6).

Extracts individual factual claims from candidate marketing drafts, preserving:
- Exact original claim text
- Exact start_char and end_char offsets within the draft
- Claim categorization (price, discount_percent, date, delivery, product_feature, other)
- Full support for English, Hindi, and Hinglish copy.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

import httpx

from app.core.config import settings
from app.schemas.verification import ExtractedClaim


# Regex patterns for deterministic extraction & classification
PRICE_RE = re.compile(r"(?:(?:INR|₹|Rs\.?)\s*\d+(?:,\d+)*(?:\.\d+)?|\b\d+(?:,\d+)*\s*(?:INR|rupees)\b)", re.IGNORECASE)
PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?%\s*(?:off|discount|flat)?|\b(?:flat|discount of)\s*\d+(?:\.\d+)?%", re.IGNORECASE)
DATE_RE = re.compile(r"\b(?:valid\s+(?:from|until|till)|from\s+[A-Za-z]+\s+\d{1,2}|to\s+[A-Za-z]+\s+\d{1,2}|\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+(?:\s+\d{4})?)\b", re.IGNORECASE)
DELIVERY_RE = re.compile(r"\b(?:\d+[\s-]*(?:hour|hr|day|business day|ghante|din)s?\s+delivery|free delivery|guaranteed delivery)\b", re.IGNORECASE)
FEATURE_RE = re.compile(r"\b(?:formulated with|contains|pure|solid sheesham|spf\s*\d+|dermatologist[- ]tested|warranty|guarantee|bana hai|upayukt)\b", re.IGNORECASE)


class ClaimExtractor:
    """
    Extracts factual marketing claims from copy.
    Uses LLM (OpenAI / Groq) when configured, and falls back to precise
    rule-based clause extraction when offline or in tests.
    """

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout = timeout_seconds

    def extract_claims(self, draft_text: str) -> List[ExtractedClaim]:
        """
        Extract factual claims from *draft_text*, ensuring each claim maps
        to exact character positions within the source draft.
        """
        clean_text = draft_text.strip()
        if not clean_text:
            return []

        # Attempt LLM extraction if API key is configured
        if settings.GROQ_API_KEY or settings.OPENAI_API_KEY:
            try:
                llm_claims = self._extract_via_llm(clean_text)
                if llm_claims:
                    return llm_claims
            except Exception:
                # LLM failure or timeout -> failover to deterministic extractor
                pass

        # Deterministic extraction fallback
        return self._extract_deterministically(clean_text)

    def _extract_via_llm(self, draft_text: str) -> List[ExtractedClaim]:
        """
        Call LLM for structured claim extraction and compute exact character offsets.
        """
        system_prompt = (
            "You are an expert factual claim extraction system for marketing content.\n"
            "Extract every distinct factual claim made in the draft.\n"
            "Do NOT paraphrase. The 'text' field MUST be an EXACT substring of the draft.\n"
            "Categories: 'price', 'discount_percent', 'date', 'delivery', 'product_feature', 'other'.\n"
            "Return valid JSON array: [{\"text\": \"exact substring\", \"type\": \"category\"}]"
        )

        headers = {"Content-Type": "application/json"}
        if settings.GROQ_API_KEY:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers["Authorization"] = f"Bearer {settings.GROQ_API_KEY}"
            model_name = "llama-3.1-8b-instant"
        else:
            url = "https://api.openai.com/v1/chat/completions"
            headers["Authorization"] = f"Bearer {settings.OPENAI_API_KEY}"
            model_name = "gpt-4o-mini"

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract all factual claims from this draft:\n\n{draft_text}"},
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"} if "gpt" in model_name else None,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"]

        # Parse JSON
        parsed = json.loads(raw_content)
        items = parsed if isinstance(parsed, list) else parsed.get("claims", [])

        results: List[ExtractedClaim] = []
        search_start = 0
        for item in items:
            c_text = item.get("text", "").strip()
            c_type = item.get("type", "other")
            if not c_text:
                continue

            pos = draft_text.find(c_text, search_start)
            if pos == -1:
                pos = draft_text.find(c_text)

            if pos != -1:
                end_pos = pos + len(c_text)
                results.append(
                    ExtractedClaim(
                        text=c_text,
                        type=c_type,
                        start_char=pos,
                        end_char=end_pos,
                    )
                )
                search_start = end_pos

        return results

    def _extract_deterministically(self, draft_text: str) -> List[ExtractedClaim]:
        """
        Split draft by punctuation boundaries (including sentences and key clauses)
        and extract verifiable factual units with exact character offsets.
        """
        # Split on sentence enders and major conjunction/clause markers
        # delimiters: . ! ? \n and semicolons
        clause_pattern = re.compile(r"([^.!?\n;]+(?:[.!?\n;]|$))", re.UNICODE)
        matches = list(clause_pattern.finditer(draft_text))

        claims: List[ExtractedClaim] = []
        for match in matches:
            raw_segment = match.group(0)
            start = match.start()
            end = match.end()

            # Clean trailing punctuation for the text content
            segment = raw_segment.strip()
            if not segment or len(segment) < 4:
                continue

            # Check if this segment contains a factual claim
            c_type = self._classify_segment(segment)
            if c_type:
                # Find exact start and end of the trimmed segment
                seg_start = draft_text.find(segment, start)
                if seg_start != -1:
                    seg_end = seg_start + len(segment)
                    claims.append(
                        ExtractedClaim(
                            text=segment,
                            type=c_type,
                            start_char=seg_start,
                            end_char=seg_end,
                        )
                    )

        return claims

    def _classify_segment(self, segment: str) -> Optional[str]:
        """
        Categorize the segment or return None if it is purely puffery/greeting.
        """
        if PRICE_RE.search(segment):
            return "price"
        if PERCENT_RE.search(segment):
            return "discount_percent"
        if DATE_RE.search(segment):
            return "date"
        if DELIVERY_RE.search(segment):
            return "delivery"
        if FEATURE_RE.search(segment):
            return "product_feature"

        # Check for numbers indicating specs/measurements (e.g. 30ml, 2-year, 15%)
        if re.search(r"\b\d+\s*(?:ml|g|kg|cm|mm|year|years|seater|seats)\b", segment, re.IGNORECASE):
            return "product_feature"

        # General factual sentences with product or brand references
        lower = segment.lower()
        if any(w in lower for w in ["auraskin", "urbannest", "guarantee", "warranty", "policy", "discount", "free", "order"]):
            return "other"

        return None

