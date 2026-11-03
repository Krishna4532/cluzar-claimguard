"""
test_retrieval_integration.py — Real PostgreSQL integration tests for Hybrid Retrieval (Milestone 5).
Uses the real claimguard_dev PostgreSQL database with transactional rollback.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models.business import Business
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document
from app.db.models.embedding import Embedding
from app.db.session import get_db
from app.main import app
from app.retrieval.embedder import generate_embeddings
from app.retrieval.hybrid import HybridRetrievalService


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


def _seed_document_with_chunks(
    session,
    business_id_str: str,
    doc_id: str,
    title: str,
    doc_type: str,
    chunks_text: list[str],
) -> Document:
    """Helper to seed a document with chunks and precomputed embeddings."""
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
        content_hash="test_hash_" + doc_id,
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
            chunk_metadata={"chunk_size": 500},
        )
        session.add(chunk)
        session.flush()

        emb = Embedding(
            chunk_id=chunk.id,
            embedding=vec,
            embedding_model=settings.EMBEDDING_MODEL_NAME,
        )
        session.add(emb)

    session.flush()
    return doc


# =====================================================================
# Real PostgreSQL Hybrid Retrieval Tests
# =====================================================================

def test_01_hybrid_search_end_to_end(client, pg_session):
    """End-to-end POST /api/retrieval/search returns fused evidence chunks."""
    _seed_document_with_chunks(
        pg_session,
        business_id_str="biz_auraskin",
        doc_id="doc_as_catalog_01",
        title="AuraSkin 2026 Product Catalog",
        doc_type="product_catalog",
        chunks_text=[
            "AuraSkin Radiance Glow Vitamin C Serum contains 15% Ethyl Ascorbic Acid and costs INR 899.",
            "HydraDew Hyaluronic Gel Moisturizer is priced at INR 649 and provides 72-hour hydration.",
            "Clarifying Salicylic Acid Cleanser unclogs pores and costs INR 549.",
        ],
    )

    resp = client.post(
        "/api/retrieval/search",
        json={
            "business_id": "biz_auraskin",
            "query": "Vitamin C Serum price INR 899",
            "top_k": 3,
        },
    )
    assert resp.status_code == 200, resp.json()
    data = resp.json()
    assert data["business_id"] == "biz_auraskin"
    assert data["total_results"] > 0
    top_chunk = data["results"][0]
    assert "Vitamin C Serum" in top_chunk["content"]
    assert top_chunk["document_id"] == "doc_as_catalog_01"
    assert top_chunk["document_title"] == "AuraSkin 2026 Product Catalog"
    assert top_chunk["rrf_score"] > 0.0


def test_02_business_tenant_isolation(client, pg_session):
    """Chunks belonging to UrbanNest are never retrieved for AuraSkin."""
    _seed_document_with_chunks(
        pg_session,
        business_id_str="biz_urbannest",
        doc_id="doc_un_sofa_01",
        title="UrbanNest Sofa Catalog",
        doc_type="product_catalog",
        chunks_text=[
            "UrbanNest CloudRest 3-Seater Velvet Sofa is priced at INR 45,999 in Emerald Green.",
        ],
    )

    # Search for UrbanNest content under AuraSkin
    resp = client.post(
        "/api/retrieval/search",
        json={
            "business_id": "biz_auraskin",
            "query": "CloudRest Velvet Sofa Emerald Green INR 45,999",
            "top_k": 5,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Must NOT return the UrbanNest sofa chunk!
    for result in data["results"]:
        assert "CloudRest" not in result["content"]
        assert result["document_id"] != "doc_un_sofa_01"


def test_03_exact_numbers_and_currency_bm25_boost(client, pg_session):
    """Exact currency and numbers like ₹24,999 are surfaced accurately via BM25."""
    _seed_document_with_chunks(
        pg_session,
        business_id_str="biz_urbannest",
        doc_id="doc_un_pricing_01",
        title="UrbanNest Price Sheet",
        doc_type="pricing",
        chunks_text=[
            "Nordic Solid Sheesham Wood Dining Table costs ₹24,999 with 15% festive discount.",
            "Minimalist Oak Coffee Table is priced at ₹9,499 with free assembly.",
        ],
    )

    resp = client.post(
        "/api/retrieval/search",
        json={
            "business_id": "biz_urbannest",
            "query": "Sheesham Dining Table ₹24,999",
            "top_k": 1,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1
    assert "₹24,999" in data["results"][0]["content"]
    assert data["results"][0]["bm25_rank"] is not None


def test_04_unknown_business_returns_404(client):
    """Searching for a non-existent business returns HTTP 404."""
    resp = client.post(
        "/api/retrieval/search",
        json={
            "business_id": "biz_nonexistent_xyz",
            "query": "Vitamin C Serum",
        },
    )
    assert resp.status_code == 404
    assert "does not exist" in resp.json()["detail"].lower()


def test_05_empty_query_returns_422(client):
    """Empty or whitespace-only query returns HTTP 422."""
    resp = client.post(
        "/api/retrieval/search",
        json={
            "business_id": "biz_auraskin",
            "query": "   ",
        },
    )
    assert resp.status_code == 422


def test_06_business_with_zero_chunks_returns_empty_safely(client):
    """A business with 0 active chunks returns 200 with an empty list."""
    resp = client.post(
        "/api/retrieval/search",
        json={
            "business_id": "biz_auraskin",
            "query": "Non-existent product query",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] == 0
    assert data["results"] == []

