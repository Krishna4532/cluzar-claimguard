"""
test_review_integration.py — Real PostgreSQL integration tests for Milestone 7
Human Review Workflow.

Uses transactional rollback fixtures against claimguard_dev.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models.business import Business
from app.db.models.claim import Claim
from app.db.models.draft import Draft
from app.db.models.verification import HumanReview, Verification, VerificationEvidence
from app.db.session import get_db
from app.main import app


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pg_engine():
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    connection = pg_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    for biz_id, name, industry in [
        ("biz_auraskin", "AuraSkin", "Skincare"),
        ("biz_urbannest", "UrbanNest", "Furniture"),
    ]:
        existing = session.execute(
            select(Business).filter_by(business_id=biz_id)
        ).scalar_one_or_none()
        if not existing:
            session.add(Business(business_id=biz_id, name=name, industry=industry))
            session.flush()

    yield session
    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def client(pg_session):
    def _override_get_db():
        try:
            yield pg_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


def _seed_reviewable_verification(
    session,
    business_id_str: str = "biz_auraskin",
    verdict: str = "needs_human",
    draft_content: str = "AuraSkin cream removes dark spots in 2 days.",
    claim_text: str = "removes dark spots in 2 days",
):
    """Helper to seed Draft -> Claim -> Verification -> Evidence chain."""
    biz = session.execute(
        select(Business).filter_by(business_id=business_id_str)
    ).scalar_one()

    draft = Draft(
        business_id=biz.id,
        content=draft_content,
        status="flagged",
    )
    session.add(draft)
    session.flush()

    claim = Claim(
        draft_id=draft.id,
        claim_text=claim_text,
        claim_type="efficacy_claim",
        start_char=16,
        end_char=44,
    )
    session.add(claim)
    session.flush()

    verif = Verification(
        claim_id=claim.id,
        verdict=verdict,
        confidence=0.55,
        rationale="Borderline clinical trial evidence.",
    )
    session.add(verif)
    session.flush()

    evidence = VerificationEvidence(
        verification_id=verif.id,
        chunk_id=None,
        evidence_text="Clinical trials showed visible improvement over 4 weeks.",
        relevance_score=0.82,
    )
    session.add(evidence)
    session.flush()

    return draft, claim, verif, evidence


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_get_review_context(client, pg_session):
    """GET /api/verifications/{id}/review returns draft, claims, evidence, and eligibility."""
    draft, claim, verif, evidence = _seed_reviewable_verification(pg_session)

    resp = client.get(f"/api/verifications/{verif.id}/review")
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["verification_id"] == verif.id
    assert data["draft_id"] == draft.id
    assert data["business_id"] == "biz_auraskin"
    assert data["draft_content"] == draft.content
    assert data["total_claims"] == 1
    assert data["pending_review_count"] == 1

    claim_item = data["claims"][0]
    assert claim_item["claim_id"] == claim.id
    assert claim_item["verdict"] == "needs_human"
    assert claim_item["eligible_for_review"] is True
    assert claim_item["human_decision"] is None
    assert len(claim_item["evidence"]) == 1
    assert claim_item["evidence"][0]["evidence_text"] == evidence.evidence_text


def test_submit_approved_decision(client, pg_session):
    """POST /api/verifications/{id}/review approves a needs_human claim."""
    _, claim, verif, _ = _seed_reviewable_verification(pg_session)

    resp = client.post(
        f"/api/verifications/{verif.id}/review",
        json={"decision": "approved", "notes": "Approved per Medical Officer sign-off."},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["verification_id"] == verif.id
    assert data["claim_id"] == claim.id
    assert data["automated_verdict"] == "needs_human"
    assert data["human_decision"] == "approved"
    assert data["notes"] == "Approved per Medical Officer sign-off."
    assert "review_id" in data


def test_submit_rejected_decision(client, pg_session):
    """POST /api/verifications/{id}/review rejects an unsupported claim."""
    _, claim, verif, _ = _seed_reviewable_verification(pg_session, verdict="unsupported")

    resp = client.post(
        f"/api/verifications/{verif.id}/review",
        json={"decision": "rejected", "notes": "No clinical evidence supporting 2 days."},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["verification_id"] == verif.id
    assert data["claim_id"] == claim.id
    assert data["automated_verdict"] == "unsupported"
    assert data["human_decision"] == "rejected"


def test_decision_persisted_in_db(client, pg_session):
    """Review decision is persistently stored in human_reviews table."""
    _, _, verif, _ = _seed_reviewable_verification(pg_session)

    client.post(
        f"/api/verifications/{verif.id}/review",
        json={"decision": "approved", "notes": "Persist check"},
    )

    review_row = pg_session.execute(
        select(HumanReview).where(HumanReview.verification_id == verif.id)
    ).scalar_one_or_none()

    assert review_row is not None
    assert review_row.reviewer_decision == "approved"
    assert review_row.reviewer_notes == "Persist check"


def test_duplicate_submission_rejected(client, pg_session):
    """Submitting human review twice for the same verification returns 409 Conflict."""
    _, _, verif, _ = _seed_reviewable_verification(pg_session)

    resp1 = client.post(
        f"/api/verifications/{verif.id}/review",
        json={"decision": "approved"},
    )
    assert resp1.status_code == 201

    resp2 = client.post(
        f"/api/verifications/{verif.id}/review",
        json={"decision": "rejected"},
    )
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"].lower()


def test_ineligible_claim_rejected(client, pg_session):
    """Claims with verdict 'supported' or 'contradicted' cannot receive human reviews (422)."""
    _, _, verif_sup, _ = _seed_reviewable_verification(pg_session, verdict="supported")

    resp = client.post(
        f"/api/verifications/{verif_sup.id}/review",
        json={"decision": "approved"},
    )
    assert resp.status_code == 422
    assert "eligible" in resp.json()["detail"].lower()

    _, _, verif_con, _ = _seed_reviewable_verification(pg_session, verdict="contradicted")
    resp_con = client.post(
        f"/api/verifications/{verif_con.id}/review",
        json={"decision": "rejected"},
    )
    assert resp_con.status_code == 422


def test_unknown_verification_404(client):
    """Accessing non-existent verification returns 404."""
    resp_get = client.get("/api/verifications/999999/review")
    assert resp_get.status_code == 404

    resp_post = client.post(
        "/api/verifications/999999/review",
        json={"decision": "approved"},
    )
    assert resp_post.status_code == 404


def test_claim_id_validation(client, pg_session):
    """Providing a mismatched claim_id returns 400; matching claim_id succeeds."""
    _, claim, verif, _ = _seed_reviewable_verification(pg_session)

    # Mismatched claim_id
    bad_resp = client.post(
        f"/api/verifications/{verif.id}/review",
        json={"claim_id": claim.id + 999, "decision": "approved"},
    )
    assert bad_resp.status_code == 400
    assert "does not match" in bad_resp.json()["detail"].lower()

    # Correct claim_id
    good_resp = client.post(
        f"/api/verifications/{verif.id}/review",
        json={"claim_id": claim.id, "decision": "approved"},
    )
    assert good_resp.status_code == 201


def test_original_verdict_preserved(client, pg_session):
    """Automated verdict in Verification table is NEVER modified by human review."""
    _, _, verif, _ = _seed_reviewable_verification(pg_session, verdict="needs_human")
    verif_id = verif.id

    client.post(
        f"/api/verifications/{verif_id}/review",
        json={"decision": "approved", "notes": "Overriding automated flag"},
    )

    verif_after = pg_session.execute(
        select(Verification).where(Verification.id == verif_id)
    ).scalar_one()

    # Verdict remains "needs_human", not "approved" or "supported"
    assert verif_after.verdict == "needs_human"


def test_pending_review_count_updates(client, pg_session):
    """GET reflects updated pending_review_count and reviewer decision after POST."""
    draft, claim1, verif1, _ = _seed_reviewable_verification(pg_session, verdict="needs_human")

    # Add second claim to the same draft
    claim2 = Claim(
        draft_id=draft.id,
        claim_text="Free shipping across India",
        claim_type="shipping",
        start_char=0,
        end_char=26,
    )
    pg_session.add(claim2)
    pg_session.flush()

    verif2 = Verification(
        claim_id=claim2.id,
        verdict="unsupported",
        confidence=0.4,
        rationale="No shipping docs found.",
    )
    pg_session.add(verif2)
    pg_session.flush()

    # Before review: pending count is 2
    resp_before = client.get(f"/api/verifications/{verif1.id}/review")
    assert resp_before.status_code == 200
    assert resp_before.json()["pending_review_count"] == 2

    # Review verif1
    client.post(
        f"/api/verifications/{verif1.id}/review",
        json={"decision": "approved", "notes": "Approved shipping promo"},
    )

    # After review: pending count is now 1
    resp_after = client.get(f"/api/verifications/{verif1.id}/review")
    assert resp_after.status_code == 200
    data_after = resp_after.json()
    assert data_after["pending_review_count"] == 1

    # Check that claim1 has decision attached
    c1 = next(c for c in data_after["claims"] if c["claim_id"] == claim1.id)
    assert c1["human_decision"] == "approved"
    assert c1["reviewer_notes"] == "Approved shipping promo"
    assert c1["reviewed_at"] is not None


def test_transaction_rollback_on_failure(client, pg_session, monkeypatch):
    """Database rollback triggers cleanly if commit fails."""
    _, _, verif, _ = _seed_reviewable_verification(pg_session)
    verif_id = verif.id

    def _failing_commit():
        raise RuntimeError("Simulated DB write failure")

    monkeypatch.setattr(pg_session, "commit", _failing_commit)

    with pytest.raises(RuntimeError, match="Simulated DB write failure"):
        client.post(
            f"/api/verifications/{verif_id}/review",
            json={"decision": "approved"},
        )

    monkeypatch.undo()

    # Ensure no human review was committed
    review_row = pg_session.execute(
        select(HumanReview).where(HumanReview.verification_id == verif_id)
    ).scalar_one_or_none()
    assert review_row is None

