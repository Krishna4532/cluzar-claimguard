"""
test_verification_integration.py — Real PostgreSQL integration tests for the
Claim Extraction and Verification Engine (Milestone 6).

Uses transactional rollback fixtures against claimguard_dev.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models.business import Business
from app.db.models.chunk import DocumentChunk
from app.db.models.claim import Claim
from app.db.models.document import Document
from app.db.models.draft import Draft
from app.db.models.embedding import Embedding
from app.db.models.verification import Verification, VerificationEvidence
from app.db.session import get_db
from app.main import app
from app.retrieval.embedder import generate_embeddings


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


def _seed_chunks(session, business_id_str, doc_id, title, doc_type, chunks_text):
    """Seed a document with chunks and embeddings for retrieval tests."""
    biz = session.execute(
        select(Business).where(Business.business_id == business_id_str)
    ).scalar_one()

    doc = Document(
        document_id=doc_id,
        business_id=biz.id,
        document_type=doc_type,
        title=title,
        file_type="txt",
        content=" ".join(chunks_text),
        content_hash="hash_" + doc_id,
        version=1,
        status="active",
        doc_metadata={},
    )
    session.add(doc)
    session.flush()

    vectors = generate_embeddings(chunks_text)
    for idx, (text, vec) in enumerate(zip(chunks_text, vectors)):
        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=idx,
            content=text,
            start_char=0,
            end_char=len(text),
            chunk_metadata={},
        )
        session.add(chunk)
        session.flush()
        session.add(Embedding(
            chunk_id=chunk.id,
            embedding=vec,
            embedding_model=settings.EMBEDDING_MODEL_NAME,
        ))
    session.flush()


@pytest.fixture
def seeded_auraskin(pg_session):
    """Seed AuraSkin product catalog, pricing, and shipping evidence."""
    _seed_chunks(
        pg_session,
        "biz_auraskin",
        "doc_as_verif_01",
        "AuraSkin 2026 Product Catalog",
        "product_catalog",
        [
            "Radiance Glow Vitamin C Serum: INR 899 (30ml). Formulated with 15% Ethyl Ascorbic Acid, Ferulic Acid, and Hyaluronic Acid. Vegan, fragrance-free, dermatologist-tested.",
            "HydraDew Hyaluronic Gel Moisturizer: INR 649 (50ml). Provides 72-hour hydration with SPF 30 protection.",
            "Clarifying Salicylic Acid Face Cleanser: INR 549 (120ml). Contains 2% Salicylic Acid.",
        ],
    )
    _seed_chunks(
        pg_session,
        "biz_auraskin",
        "doc_as_verif_02",
        "AuraSkin Festive Glow Offer",
        "offer",
        [
            "Flat 20% discount on eligible AuraSkin products. Valid from October 15, 2026 to November 15, 2026 with a minimum order value of INR 999.",
            "Clarifying Salicylic Acid Face Cleanser is strictly excluded from this offer.",
        ],
    )
    _seed_chunks(
        pg_session,
        "biz_auraskin",
        "doc_as_verif_03",
        "AuraSkin Shipping Policy",
        "policy",
        [
            "Metro cities (Delhi-NCR, Mumbai, Bengaluru, Hyderabad, Chennai, Kolkata) receive delivery within 2 to 3 business days. Non-metro locations take 4 to 6 business days.",
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_v01_supported_price_claim(client, seeded_auraskin):
    """A correct price claim (INR 899) is verified as supported."""
    resp = client.post("/api/verifications/check", json={
        "business_id": "biz_auraskin",
        "draft_text": "Our Radiance Glow Vitamin C Serum is available for just INR 899.",
    })
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["total_claims"] >= 1
    price_claims = [c for c in data["claims"] if "899" in c["text"]]
    assert len(price_claims) >= 1
    assert price_claims[0]["verdict"] == "supported"


def test_v02_contradicted_price_claim(client, seeded_auraskin):
    """A wrong price claim (INR 799 vs actual INR 899) is contradicted."""
    resp = client.post("/api/verifications/check", json={
        "business_id": "biz_auraskin",
        "draft_text": "Get AuraSkin Radiance Glow Vitamin C Serum for only INR 799!",
    })
    assert resp.status_code == 200
    data = resp.json()
    price_claims = [c for c in data["claims"] if "799" in c["text"]]
    assert len(price_claims) >= 1
    assert price_claims[0]["verdict"] == "contradicted"
    assert data["overall_status"] == "rejected"


def test_v03_contradicted_delivery_claim(client, seeded_auraskin):
    """A 24-hour delivery promise contradicts a 2-3 business day shipping policy."""
    resp = client.post("/api/verifications/check", json={
        "business_id": "biz_auraskin",
        "draft_text": "Enjoy guaranteed 24-hour delivery anywhere in India with AuraSkin!",
    })
    assert resp.status_code == 200
    data = resp.json()
    delivery_claims = [c for c in data["claims"] if "delivery" in c["text"].lower() or c["type"] == "delivery"]
    assert len(delivery_claims) >= 1
    assert delivery_claims[0]["verdict"] == "contradicted"


def test_v04_unsupported_claim_no_evidence(client, pg_session):
    """A verifiable claim about a non-existent product with no matching evidence is unsupported."""
    # Seed only irrelevant evidence — nothing about "Anti-Aging Night Cream"
    _seed_chunks(
        pg_session,
        "biz_auraskin",
        "doc_as_verif_empty",
        "AuraSkin Empty Catalog",
        "product_catalog",
        ["AuraSkin Headquarters is located in Mumbai."],
    )
    resp = client.post("/api/verifications/check", json={
        "business_id": "biz_auraskin",
        "draft_text": "AuraSkin Anti-Aging Night Cream costs INR 1299 and includes free delivery.",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_claims"] >= 1
    # Claims should be unsupported or needs_human (no matching evidence exists)
    for claim in data["claims"]:
        assert claim["verdict"] in ("unsupported", "needs_human", "contradicted"), (
            f"Unexpected verdict '{claim['verdict']}' for claim with no matching evidence: {claim['text']}"
        )
    assert data["overall_status"] in ("flagged", "rejected")


def test_v05_business_isolation_verification(client, seeded_auraskin, pg_session):
    """UrbanNest draft must not retrieve AuraSkin evidence."""
    _seed_chunks(
        pg_session,
        "biz_urbannest",
        "doc_un_verif_01",
        "UrbanNest Pricing",
        "pricing",
        ["Nordic Solid Sheesham Wood Dining Table costs ₹24,999 with 15% festive discount."],
    )
    resp = client.post("/api/verifications/check", json={
        "business_id": "biz_urbannest",
        "draft_text": "Our Radiance Glow Vitamin C Serum costs INR 899.",
    })
    assert resp.status_code == 200
    data = resp.json()
    # UrbanNest has no serum documents. Evidence should not cross from AuraSkin
    for claim in data["claims"]:
        for ev in claim.get("evidence", []):
            assert ev.get("document_id", "").startswith("doc_un") or ev.get("document_id") is None, (
                f"Cross-tenant evidence leakage detected: {ev.get('document_id')}"
            )


def test_v06_draft_and_claims_persisted(client, seeded_auraskin, pg_session):
    """Draft, Claims, Verification, and VerificationEvidence rows are persisted."""
    resp = client.post("/api/verifications/check", json={
        "business_id": "biz_auraskin",
        "draft_text": "AuraSkin Radiance Glow Vitamin C Serum costs INR 899.",
    })
    assert resp.status_code == 200
    draft_id = resp.json()["draft_id"]

    draft = pg_session.execute(
        select(Draft).where(Draft.id == draft_id)
    ).scalar_one_or_none()
    assert draft is not None

    claim_count = pg_session.execute(
        select(func.count(Claim.id)).where(Claim.draft_id == draft_id)
    ).scalar_one()
    assert claim_count >= 1

    claims = pg_session.execute(
        select(Claim).where(Claim.draft_id == draft_id)
    ).scalars().all()
    for claim in claims:
        verif_count = pg_session.execute(
            select(func.count(Verification.id)).where(Verification.claim_id == claim.id)
        ).scalar_one()
        assert verif_count >= 1


def test_v07_unknown_business_returns_404(client):
    """Verification check for non-existent business returns 404."""
    resp = client.post("/api/verifications/check", json={
        "business_id": "biz_nonexistent_xyz",
        "draft_text": "Some marketing copy.",
    })
    assert resp.status_code == 404


def test_v08_empty_draft_returns_422(client):
    """Empty draft text returns 422."""
    resp = client.post("/api/verifications/check", json={
        "business_id": "biz_auraskin",
        "draft_text": "   ",
    })
    assert resp.status_code == 422


def test_v09_overall_status_rejected_when_any_contradicted(client, seeded_auraskin):
    """If any claim is contradicted, overall_status must be 'rejected'."""
    resp = client.post("/api/verifications/check", json={
        "business_id": "biz_auraskin",
        "draft_text": "AuraSkin Vitamin C Serum for INR 799 with guaranteed 24-hour delivery!",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["contradicted_count"] >= 1
    assert data["overall_status"] == "rejected"

