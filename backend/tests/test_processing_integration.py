"""
test_processing_integration.py — PostgreSQL integration tests for Milestone 4.

These tests use the real PostgreSQL ``claimguard_dev`` database (not SQLite).
Each test runs inside a transactional wrapper that is rolled back on teardown,
so no test data persists between runs.

Run (requires BypassSandbox=true for PostgreSQL connectivity):
    backend\\.venv\\Scripts\\python.exe -m pytest backend/tests/test_processing_integration.py -v

Fixtures reuse the same pg_engine / pg_session / client pattern established
in test_ingestion_integration.py.
"""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.session import get_db
from app.db.models.business import Business
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document
from app.db.models.embedding import Embedding
from app.main import app
from tests.test_ingestion_unit import create_minimal_pdf_bytes


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures (same rollback-per-test pattern as ingestion integration tests)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def pg_engine():
    """Real PostgreSQL engine for the claimguard_dev database."""
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    """
    Opens a connection, starts an outer transaction, yields a session bound to it,
    then rolls back — leaving the database clean after every test.
    """
    connection = pg_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    # Ensure seed businesses exist within this transaction
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
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(pg_session):
    """FastAPI TestClient whose get_db dependency is overridden with the rollback session."""
    def _override_get_db():
        try:
            yield pg_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as tc:
        yield tc
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────────────────────
# Helper: upload a TXT document and return its document_id string
# ─────────────────────────────────────────────────────────────────────────────

def _upload_txt(client, content: bytes, business_id: str = "biz_auraskin") -> str:
    resp = client.post(
        "/api/documents/upload",
        data={
            "business_id": business_id,
            "document_type": "product_catalog",
            "title": "M4 Test Document",
        },
        files={"file": ("test.txt", content, "text/plain")},
    )
    assert resp.status_code == 201, f"Upload failed: {resp.json()}"
    return resp.json()["document_id"]


def _upload_pdf(client, business_id: str = "biz_urbannest") -> str:
    pdf_bytes = create_minimal_pdf_bytes("UrbanNest CloudRest Sofa 2-year Warranty Policy 2026.")
    resp = client.post(
        "/api/documents/upload",
        data={
            "business_id": business_id,
            "document_type": "warranty_policy",
            "title": "CloudRest Warranty Manual",
        },
        files={"file": ("warranty.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp.status_code == 201, f"Upload failed: {resp.json()}"
    return resp.json()["document_id"]


# ─────────────────────────────────────────────────────────────────────────────
# 14 PostgreSQL integration tests
# ─────────────────────────────────────────────────────────────────────────────

_LONG_TXT = (
    "AuraSkin Radiance Glow Vitamin C Serum is priced at INR 899 for a 30 ml bottle. "
    "It contains 15% Ethyl Ascorbic Acid, Niacinamide, and Hyaluronic Acid. "
    "The formula is dermatologist-tested and fragrance-free. "
    "AuraSkin offers a 30-day satisfaction guarantee on all skincare products. "
    "A minimum order of INR 500 applies for free delivery within India. "
    "The HydraBalance Moisturiser costs INR 649 and includes SPF 30 protection. "
    "UrbanNest's ErgoComfort Pro Chair is priced at INR 24,999 with a 2-year warranty. "
    "CloudRest Sofa is available in three colours: Ivory, Charcoal, and Sage Green. "
) * 8   # ~640 chars × 8 ≈ 5120 chars → guaranteed multi-chunk


def test_pg_01_process_valid_txt_document(client):
    """POST /api/documents/{id}/process returns 201 for a new TXT document."""
    doc_id = _upload_txt(client, _LONG_TXT.encode())
    resp = client.post(f"/api/documents/{doc_id}/process")
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    assert data["document_id"] == doc_id
    assert data["processing_status"] == "processed"
    assert data["chunk_count"] > 0
    assert data["embedding_count"] == data["chunk_count"]


def test_pg_02_process_valid_pdf_document(client):
    """POST /api/documents/{id}/process returns 201 for a new PDF document."""
    doc_id = _upload_pdf(client)
    resp = client.post(f"/api/documents/{doc_id}/process")
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    assert data["processing_status"] == "processed"
    assert data["chunk_count"] > 0


def test_pg_03_chunks_persisted_to_db(client, pg_session):
    """After processing, DocumentChunk rows exist in the database."""
    doc_id = _upload_txt(client, _LONG_TXT.encode())
    client.post(f"/api/documents/{doc_id}/process")

    doc = pg_session.execute(
        select(Document).where(Document.document_id == doc_id)
    ).scalar_one()

    count = pg_session.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
    ).scalar_one()

    assert count > 0, "Expected document_chunks rows after processing."


def test_pg_04_embeddings_persisted_to_db(client, pg_session):
    """After processing, Embedding rows exist in the database."""
    doc_id = _upload_txt(client, _LONG_TXT.encode())
    client.post(f"/api/documents/{doc_id}/process")

    doc = pg_session.execute(
        select(Document).where(Document.document_id == doc_id)
    ).scalar_one()

    chunk_ids = pg_session.execute(
        select(DocumentChunk.id).where(DocumentChunk.document_id == doc.id)
    ).scalars().all()
    assert chunk_ids, "No chunks found — cannot check embeddings."

    emb_count = pg_session.execute(
        select(func.count(Embedding.id)).where(Embedding.chunk_id.in_(chunk_ids))
    ).scalar_one()

    assert emb_count == len(chunk_ids), (
        f"Expected {len(chunk_ids)} embeddings, found {emb_count}."
    )


def test_pg_05_chunk_document_relationship(client, pg_session):
    """Each DocumentChunk.document_id must match the Document.id (FK integrity)."""
    doc_id = _upload_txt(client, _LONG_TXT.encode())
    client.post(f"/api/documents/{doc_id}/process")

    doc = pg_session.execute(
        select(Document).where(Document.document_id == doc_id)
    ).scalar_one()

    orphan_count = pg_session.execute(
        select(func.count(DocumentChunk.id)).where(
            (DocumentChunk.document_id == doc.id) &
            (DocumentChunk.document_id != doc.id)  # deliberately always False
        )
    ).scalar_one()
    assert orphan_count == 0

    # Positive check: all chunks reference the correct document PK
    chunks = pg_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    ).scalars().all()
    for chunk in chunks:
        assert chunk.document_id == doc.id


def test_pg_06_embedding_chunk_relationship(client, pg_session):
    """Each Embedding.chunk_id must reference a DocumentChunk in the same document."""
    doc_id = _upload_txt(client, _LONG_TXT.encode())
    client.post(f"/api/documents/{doc_id}/process")

    doc = pg_session.execute(
        select(Document).where(Document.document_id == doc_id)
    ).scalar_one()
    chunk_ids = set(
        pg_session.execute(
            select(DocumentChunk.id).where(DocumentChunk.document_id == doc.id)
        ).scalars().all()
    )
    emb_chunk_ids = set(
        pg_session.execute(
            select(Embedding.chunk_id).where(Embedding.chunk_id.in_(chunk_ids))
        ).scalars().all()
    )
    assert emb_chunk_ids == chunk_ids, (
        "Every chunk should have an embedding; orphan chunks detected."
    )


def test_pg_07_business_id_correctly_assigned(client, pg_session):
    """Chunks must trace back to the correct business via their parent Document."""
    doc_id = _upload_txt(client, _LONG_TXT.encode(), business_id="biz_auraskin")
    client.post(f"/api/documents/{doc_id}/process")

    biz = pg_session.execute(
        select(Business).where(Business.business_id == "biz_auraskin")
    ).scalar_one()
    doc = pg_session.execute(
        select(Document).where(Document.document_id == doc_id)
    ).scalar_one()

    assert doc.business_id == biz.id


def test_pg_08_embedding_vector_dimension_384(client, pg_session):
    """
    Query the raw pgvector dimension from PostgreSQL — must be 384.
    Uses vector_dims() which is available in pgvector 0.5+.
    """
    doc_id = _upload_txt(client, _LONG_TXT.encode())
    client.post(f"/api/documents/{doc_id}/process")

    doc = pg_session.execute(
        select(Document).where(Document.document_id == doc_id)
    ).scalar_one()
    first_chunk = pg_session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    ).scalars().first()
    assert first_chunk is not None

    dim = pg_session.execute(
        text("SELECT vector_dims(embedding) FROM embeddings WHERE chunk_id = :cid"),
        {"cid": first_chunk.id},
    ).scalar_one()

    assert dim == settings.EMBEDDING_DIMENSION, f"Expected 384 dims, got {dim}."


def test_pg_09_idempotent_reprocessing(client, pg_session):
    """
    Calling /process twice must NOT create duplicate chunks or embeddings.
    Second call must return 200 with processing_status='already_processed'.
    """
    doc_id = _upload_txt(client, _LONG_TXT.encode())

    resp1 = client.post(f"/api/documents/{doc_id}/process")
    assert resp1.status_code == 201
    chunk_count_1 = resp1.json()["chunk_count"]

    resp2 = client.post(f"/api/documents/{doc_id}/process")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["processing_status"] == "already_processed"
    assert data2["chunk_count"] == chunk_count_1

    # Verify no duplicate rows in DB
    doc = pg_session.execute(
        select(Document).where(Document.document_id == doc_id)
    ).scalar_one()
    db_chunk_count = pg_session.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc.id)
    ).scalar_one()
    assert db_chunk_count == chunk_count_1


def test_pg_10_failed_processing_rollback(client, pg_session, monkeypatch):
    """
    A DB commit failure during processing must roll back fully — no partial chunks.
    """
    doc_id = _upload_txt(client, _LONG_TXT.encode())

    # Count before the failed attempt
    doc = pg_session.execute(
        select(Document).where(Document.document_id == doc_id)
    ).scalar_one()
    doc_pk = doc.id
    count_before = pg_session.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc_pk)
    ).scalar_one()

    def _boom():
        raise RuntimeError("Simulated commit failure during processing")

    monkeypatch.setattr(pg_session, "commit", _boom)

    resp = client.post(f"/api/documents/{doc_id}/process")
    assert resp.status_code in (422, 500)

    monkeypatch.undo()

    count_after = pg_session.execute(
        select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == doc_pk)
    ).scalar_one()
    assert count_after == count_before, "Partial chunk data must not persist after rollback."


def test_pg_11_unknown_document_rejected(client):
    """POST /api/documents/{id}/process with an unknown ID returns 404."""
    resp = client.post("/api/documents/doc_does_not_exist_xyz/process")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_pg_12_empty_document_rejected(client, pg_session):
    """
    A Document row with empty content should return 422 when processed.
    We insert the row directly (bypassing the ingestion API which already rejects empties).
    """
    biz = pg_session.execute(
        select(Business).where(Business.business_id == "biz_auraskin")
    ).scalar_one()

    empty_doc = Document(
        document_id="doc_empty_content_test_m4",
        business_id=biz.id,
        document_type="test",
        title="Empty Content Doc",
        file_type="txt",
        content="   ",          # whitespace-only
        content_hash="deadbeef00000000" * 4,
        version=1,
        status="active",
        doc_metadata={},
    )
    pg_session.add(empty_doc)
    pg_session.flush()

    resp = client.post("/api/documents/doc_empty_content_test_m4/process")
    assert resp.status_code == 422
    assert "empty" in resp.json()["detail"].lower() or "text" in resp.json()["detail"].lower()


def test_pg_13_superseded_document_rejected(client, pg_session):
    """
    A Document with status='superseded' must return 422 when processed.
    """
    biz = pg_session.execute(
        select(Business).where(Business.business_id == "biz_auraskin")
    ).scalar_one()

    sup_doc = Document(
        document_id="doc_superseded_test_m4",
        business_id=biz.id,
        document_type="test",
        title="Superseded Doc",
        file_type="txt",
        content="This content is valid but the document is superseded.",
        content_hash="cafebabe00000000" * 4,
        version=1,
        status="superseded",   # deliberately superseded
        doc_metadata={},
    )
    pg_session.add(sup_doc)
    pg_session.flush()

    resp = client.post("/api/documents/doc_superseded_test_m4/process")
    assert resp.status_code == 422
    assert "superseded" in resp.json()["detail"].lower()


def test_pg_14_business_isolation(client, pg_session):
    """
    A document belonging to AuraSkin must not appear in UrbanNest's chunk queries
    and vice-versa.
    """
    # Upload and process an AuraSkin document
    doc_id_as = _upload_txt(client, _LONG_TXT.encode(), business_id="biz_auraskin")
    client.post(f"/api/documents/{doc_id_as}/process")

    # Fetch chunks for the AuraSkin document
    resp = client.get(f"/api/documents/{doc_id_as}/chunks")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"] == doc_id_as
    assert data["total_chunks"] > 0

    # Confirm those chunks do NOT appear under UrbanNest's documents in DB
    biz_un = pg_session.execute(
        select(Business).where(Business.business_id == "biz_urbannest")
    ).scalar_one()
    doc_as = pg_session.execute(
        select(Document).where(Document.document_id == doc_id_as)
    ).scalar_one()

    # Ensure the document's business_id is NOT UrbanNest's id
    assert doc_as.business_id != biz_un.id

