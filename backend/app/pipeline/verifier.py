"""
verifier.py — End-to-end verification orchestrator for ClaimGuard (Milestone 6).

Coordinates:
1. Draft persistence and business validation
2. Structured claim extraction with source character offset preservation
3. Authoritative evidence retrieval via Milestone 5 HybridRetrievalService
4. Deterministic numerical/currency/percentage checking
5. Semantic LLM verification with fail-closed safety
6. Complete database persistence (Draft, Claim, Verification, VerificationEvidence)
"""

from __future__ import annotations

from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.business import Business
from app.db.models.claim import Claim
from app.db.models.draft import Draft
from app.db.models.verification import Verification, VerificationEvidence
from app.ingestion.exceptions import BusinessNotFoundError
from app.pipeline.deterministic import DeterministicVerifier
from app.pipeline.extractor import ClaimExtractor
from app.pipeline.semantic import SemanticVerifier
from app.retrieval.hybrid import HybridRetrievalService
from app.schemas.verification import (
    ClaimVerificationResult,
    EvidenceReference,
    OverallStatusType,
    VerificationCheckResponse,
)


class VerificationPipeline:
    """
    End-to-end claim extraction and verification pipeline.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.extractor = ClaimExtractor()
        self.retrieval_service = HybridRetrievalService(db)
        self.deterministic_verifier = DeterministicVerifier()
        self.semantic_verifier = SemanticVerifier()

    def verify_draft(
        self,
        business_id_str: str,
        draft_text: str,
    ) -> VerificationCheckResponse:
        """
        Verify an entire marketing draft against approved business documents.
        """
        # 1. Validate business exists
        biz_stmt = select(Business).where(Business.business_id == business_id_str)
        biz = self.db.execute(biz_stmt).scalar_one_or_none()
        if not biz:
            raise BusinessNotFoundError(business_id_str)

        # 2. Persist Draft
        draft = Draft(
            business_id=biz.id,
            content=draft_text,
            status="pending",
        )
        self.db.add(draft)
        self.db.flush()

        # 3. Extract claims
        extracted_claims = self.extractor.extract_claims(draft_text)

        results: List[ClaimVerificationResult] = []
        supported_count = 0
        contradicted_count = 0
        unsupported_count = 0
        needs_human_count = 0

        # 4. Verify each claim
        for ec in extracted_claims:
            # Retrieve evidence using Milestone 5 hybrid search
            retrieval_resp = self.retrieval_service.search(
                business_id_str=business_id_str,
                query=ec.text,
                top_k=3,
            )

            evidence_refs: List[EvidenceReference] = [
                EvidenceReference(
                    chunk_id=c.chunk_id,
                    document_id=c.document_id,
                    document_title=c.document_title,
                    source_text=c.content,
                    relevance_score=c.rrf_score,
                )
                for c in retrieval_resp.results
            ]

            # A. Try deterministic numerical verification first
            det_outcome = self.deterministic_verifier.verify(
                claim_text=ec.text,
                claim_type=ec.type,
                evidence_list=evidence_refs,
            )

            if det_outcome is not None:
                verdict, explanation, confidence = det_outcome
            else:
                # B. Semantic verification via LLM / safe fallback
                verdict, explanation, confidence = self.semantic_verifier.verify(
                    claim_text=ec.text,
                    claim_type=ec.type,
                    evidence_list=evidence_refs,
                )

            # Update counters
            if verdict == "supported":
                supported_count += 1
            elif verdict == "contradicted":
                contradicted_count += 1
            elif verdict == "unsupported":
                unsupported_count += 1
            elif verdict == "needs_human":
                needs_human_count += 1

            # 5. Persist Claim & Verification
            claim_row = Claim(
                draft_id=draft.id,
                claim_text=ec.text,
                claim_type=ec.type,
                start_char=ec.start_char,
                end_char=ec.end_char,
            )
            self.db.add(claim_row)
            self.db.flush()

            verif_row = Verification(
                claim_id=claim_row.id,
                verdict=verdict,
                rationale=explanation,
                confidence=confidence,
            )
            self.db.add(verif_row)
            self.db.flush()

            for ev in evidence_refs:
                ev_row = VerificationEvidence(
                    verification_id=verif_row.id,
                    chunk_id=ev.chunk_id,
                    relevance_score=ev.relevance_score,
                    evidence_text=ev.source_text,
                )
                self.db.add(ev_row)

            results.append(
                ClaimVerificationResult(
                    text=ec.text,
                    type=ec.type,
                    start_char=ec.start_char,
                    end_char=ec.end_char,
                    verdict=verdict,
                    explanation=explanation,
                    confidence=confidence,
                    evidence=evidence_refs,
                )
            )

        # 6. Overall Status Determination
        if contradicted_count > 0:
            overall_status: OverallStatusType = "rejected"
        elif needs_human_count > 0 or unsupported_count > 0:
            overall_status: OverallStatusType = "flagged"
        else:
            overall_status: OverallStatusType = "approved"

        draft.status = overall_status
        self.db.commit()

        return VerificationCheckResponse(
            draft_id=draft.id,
            business_id=business_id_str,
            overall_status=overall_status,
            total_claims=len(results),
            supported_count=supported_count,
            contradicted_count=contradicted_count,
            unsupported_count=unsupported_count,
            needs_human_count=needs_human_count,
            claims=results,
        )

