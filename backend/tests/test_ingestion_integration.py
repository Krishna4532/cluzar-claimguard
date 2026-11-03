import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.db.session import get_db
from app.db.models.business import Business
from app.db.models.document import Document
from tests.test_ingestion_unit import create_minimal_pdf_bytes
from pypdf import PdfWriter


@pytest.fixture(scope="module")
def pg_engine():
    """Real PostgreSQL engine connecting to the configured development database."""
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    """
    Transactional PostgreSQL test fixture.
    Runs each test inside an outer transaction and rolls it back upon test completion
    so no test documents remain in the database.
    """
    connection = pg_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    # Ensure synthetic businesses exist for the test
    for biz_id, name, industry in [
        ("biz_auraskin", "AuraSkin", "Skincare"),
        ("biz_urbannest", "UrbanNest", "Furniture"),
    ]:
        existing = session.execute(select(Business).filter_by(business_id=biz_id)).scalar_one_or_none()
        if not existing:
            session.add(Business(business_id=biz_id, name=name, industry=industry))
            session.flush()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(pg_session):
    """FastAPI TestClient with overridden get_db dependency pointing to the rollback session."""
    def _override_get_db():
        try:
            yield pg_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# =====================================================================
# REAL POSTGRESQL INTEGRATION TESTS (ALL 17 SCENARIOS)
# =====================================================================

def test_01_valid_txt_upload(client):
    """Scenario 1: Valid TXT upload returns 201, character count, version 1, and active status."""
    content = b"Radiance Glow Vitamin C Serum: INR 899 (30ml). Formulated with 15% Ethyl Ascorbic Acid."
    response = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_auraskin",
            "document_type": "product_catalog",
            "title": "AuraSkin Serum Specs 2026",
        },
        files={"file": ("specs.txt", content, "text/plain")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["business_id"] == "biz_auraskin"
    assert data["title"] == "AuraSkin Serum Specs 2026"
    assert data["file_type"] == "txt"
    assert data["version"] == 1
    assert data["status"] == "active"
    assert data["extracted_character_count"] == len(content.decode("utf-8"))
    assert len(data["file_hash"]) == 64


def test_02_valid_pdf_upload(client):
    """Scenario 2: Valid PDF upload extracts text and returns 201 with file_type 'pdf'."""
    pdf_bytes = create_minimal_pdf_bytes("UrbanNest Office Chair Warranty Guidelines 2026")
    response = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_urbannest",
            "document_type": "warranty_policy",
            "title": "ErgoComfort Warranty Manual",
        },
        files={"file": ("warranty.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["business_id"] == "biz_urbannest"
    assert data["file_type"] == "pdf"
    assert data["version"] == 1
    assert data["extracted_character_count"] > 0


def test_03_empty_file_rejection(client):
    """Scenario 3: Empty file (0 bytes) is rejected with 400 Bad Request."""
    response = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_auraskin",
            "document_type": "pricing",
            "title": "Empty File Test",
        },
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_04_unsupported_extension_rejection(client):
    """Scenario 4: Unsupported extension (e.g. .docx, .png) is rejected with 400 Bad Request."""
    response = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_auraskin",
            "document_type": "pricing",
            "title": "Word Doc Test",
        },
        files={"file": ("test.docx", b"PK\x03\x04...", "application/vnd.openxmlformats")},
    )
    assert response.status_code == 400
    assert "unsupported file extension" in response.json()["detail"].lower()


def test_05_oversized_file_rejection(client):
    """Scenario 5: File exceeding 10 MB limit is rejected with 413 Payload Too Large."""
    # 10 MB + 1024 bytes
    oversized = b"0" * (10 * 1024 * 1024 + 1024)
    response = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_auraskin",
            "document_type": "pricing",
            "title": "Oversized Test",
        },
        files={"file": ("huge.txt", oversized, "text/plain")},
    )
    assert response.status_code == 413
    assert "exceeds the maximum allowed size of 10 mb" in response.json()["detail"].lower()


def test_06_malformed_pdf_rejection(client):
    """Scenario 6: Malformed PDF without %PDF- header is rejected with 400 Bad Request."""
    corrupted_pdf = b"NOT_A_PDF_HEADER_JUST_RANDOM_TEXT"
    response = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_auraskin",
            "document_type": "product_catalog",
            "title": "Corrupt PDF",
        },
        files={"file": ("corrupt.pdf", corrupted_pdf, "application/pdf")},
    )
    assert response.status_code == 400
    assert "pdf" in response.json()["detail"].lower()


def test_07_encrypted_pdf_rejection(client):
    """Scenario 7: Encrypted / password-protected PDF is rejected with 422 Unprocessable Entity."""
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("super_secret_pw")
    buf = io.BytesIO()
    writer.write(buf)
    encrypted_bytes = buf.getvalue()

    response = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_auraskin",
            "document_type": "policy",
            "title": "Encrypted Doc",
        },
        files={"file": ("encrypted.pdf", encrypted_bytes, "application/pdf")},
    )
    assert response.status_code == 422
    assert "encrypted" in response.json()["detail"].lower()


def test_08_pdf_no_usable_text_rejection(client):
    """Scenario 8: PDF containing 0 extractable characters is rejected with 422."""
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    blank_bytes = buf.getvalue()

    response = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_urbannest",
            "document_type": "policy",
            "title": "Blank PDF Doc",
        },
        files={"file": ("blank.pdf", blank_bytes, "application/pdf")},
    )
    assert response.status_code == 422
    assert "yielded no extractable text" in response.json()["detail"].lower()


def test_09_unknown_business_rejection(client):
    """Scenario 9: Non-existent business ID is rejected with 404 Not Found."""
    response = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_nonexistent_corp",
            "document_type": "pricing",
            "title": "Orphan Doc",
        },
        files={"file": ("orphan.txt", b"Some valid content text", "text/plain")},
    )
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"].lower()


def test_10_identical_duplicate_upload_same_business(client, pg_session):
    """
    Scenario 10: Identical duplicate file uploaded for the SAME business returns
    the existing document reference and does NOT create a duplicate row in PostgreSQL.
    """
    content = b"Same business duplicate test content for AuraSkin."
    # First upload
    res1 = client.post(
        "/api/documents/upload",
        data={"business_id": "biz_auraskin", "document_type": "pricing", "title": "Dup Test"},
        files={"file": ("dup.txt", content, "text/plain")},
    )
    assert res1.status_code == 201
    doc_id_1 = res1.json()["document_id"]

    # Second upload of identical content
    res2 = client.post(
        "/api/documents/upload",
        data={"business_id": "biz_auraskin", "document_type": "pricing", "title": "Dup Test"},
        files={"file": ("dup.txt", content, "text/plain")},
    )
    assert res2.status_code == 201
    doc_id_2 = res2.json()["document_id"]

    # Returns the exact existing document ID
    assert doc_id_1 == doc_id_2

    # Verify only 1 row exists in PostgreSQL
    count = pg_session.execute(
        select(func.count(Document.id)).where(Document.document_id == doc_id_1)
    ).scalar()
    assert count == 1


def test_11_identical_content_different_business_allowed(client, pg_session):
    """
    Scenario 11: Identical content uploaded for a DIFFERENT business creates a distinct,
    independent document record scoped to the second business tenant.
    """
    shared_content = b"Standard Terms of Service text shared across corporate entities."

    # Upload for AuraSkin
    res_as = client.post(
        "/api/documents/upload",
        data={"business_id": "biz_auraskin", "document_type": "terms", "title": "Terms of Service"},
        files={"file": ("terms.txt", shared_content, "text/plain")},
    )
    assert res_as.status_code == 201

    # Upload identical bytes for UrbanNest
    res_un = client.post(
        "/api/documents/upload",
        data={"business_id": "biz_urbannest", "document_type": "terms", "title": "Terms of Service"},
        files={"file": ("terms.txt", shared_content, "text/plain")},
    )
    assert res_un.status_code == 201

    # Both documents have the same content hash but distinct document IDs and tenant ownership
    assert res_as.json()["document_id"] != res_un.json()["document_id"]
    assert res_as.json()["file_hash"] == res_un.json()["file_hash"]
    assert res_as.json()["business_id"] == "biz_auraskin"
    assert res_un.json()["business_id"] == "biz_urbannest"


def test_12_and_13_changed_document_versioning_and_preservation(client, pg_session):
    """
    Scenario 12 & 13: Uploading a changed document with identical logical identity
    (business + title + document_type) increments version to 2 and preserves version 1.
    """
    v1_content = b"Radiance Glow Serum original price: INR 899."
    v2_content = b"Radiance Glow Serum revised price: INR 949 (Q1 2027 update)."

    # 1. Upload Version 1
    res1 = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_auraskin",
            "document_type": "price_list",
            "title": "Official Serum Price List",
        },
        files={"file": ("prices_v1.txt", v1_content, "text/plain")},
    )
    assert res1.status_code == 201
    assert res1.json()["version"] == 1
    assert res1.json()["status"] == "active"
    doc_id_v1 = res1.json()["document_id"]

    # 2. Upload Changed Version 2
    res2 = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_auraskin",
            "document_type": "price_list",
            "title": "Official Serum Price List",
        },
        files={"file": ("prices_v2.txt", v2_content, "text/plain")},
    )
    assert res2.status_code == 201
    assert res2.json()["version"] == 2
    assert res2.json()["status"] == "active"
    doc_id_v2 = res2.json()["document_id"]

    # 3. Verify both versions exist in PostgreSQL
    v1_row = pg_session.execute(select(Document).where(Document.document_id == doc_id_v1)).scalar_one()
    v2_row = pg_session.execute(select(Document).where(Document.document_id == doc_id_v2)).scalar_one()

    assert v1_row.version == 1
    assert v1_row.status == "superseded"  # Preserved but superseded
    assert v2_row.version == 2
    assert v2_row.status == "active"      # Current active document


def test_14_document_metadata_retrieval(client):
    """Scenario 14: GET /api/documents/{document_id} returns accurate metadata without full text."""
    content = b"UrbanNest CloudRest Sofa Specs: Velvet Upholstery, Pine Frame."
    upload_res = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_urbannest",
            "document_type": "product_specs",
            "title": "CloudRest Specs",
        },
        files={"file": ("specs.txt", content, "text/plain")},
    )
    doc_id = upload_res.json()["document_id"]

    # Retrieve metadata
    meta_res = client.get(f"/api/documents/{doc_id}")
    assert meta_res.status_code == 200
    meta = meta_res.json()
    assert meta["document_id"] == doc_id
    assert meta["business_id"] == "biz_urbannest"
    assert meta["title"] == "CloudRest Specs"
    assert meta["page_count"] == 1
    assert meta["extracted_character_count"] == len(content)
    assert "content" not in meta  # Full text is NOT exposed in metadata endpoint


def test_15_business_scoped_document_listing(client):
    """Scenario 15: GET /api/businesses/{business_id}/documents lists all documents for tenant."""
    # Ingest 2 documents for UrbanNest
    client.post(
        "/api/documents/upload",
        data={"business_id": "biz_urbannest", "document_type": "policy", "title": "Doc A"},
        files={"file": ("a.txt", b"Content A", "text/plain")},
    )
    client.post(
        "/api/documents/upload",
        data={"business_id": "biz_urbannest", "document_type": "policy", "title": "Doc B"},
        files={"file": ("b.txt", b"Content B", "text/plain")},
    )

    list_res = client.get("/api/businesses/biz_urbannest/documents")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] >= 2
    titles = [item["title"] for item in data["items"]]
    assert "Doc A" in titles
    assert "Doc B" in titles


def test_16_cross_business_isolation(client):
    """Scenario 16: Ensure documents uploaded for UrbanNest are NOT listed under AuraSkin."""
    unique_marker_content = b"Exclusively for UrbanNest cross-tenant isolation test."
    client.post(
        "/api/documents/upload",
        data={"business_id": "biz_urbannest", "document_type": "policy", "title": "UrbanNest Exclusive Doc"},
        files={"file": ("exclusive.txt", unique_marker_content, "text/plain")},
    )

    # Query AuraSkin document list
    as_list_res = client.get("/api/businesses/biz_auraskin/documents")
    assert as_list_res.status_code == 200
    as_titles = [item["title"] for item in as_list_res.json()["items"]]
    assert "UrbanNest Exclusive Doc" not in as_titles


def test_17_transaction_rollback_on_persistence_failure(client, pg_session, monkeypatch):
    """
    Scenario 17: Database failure during document persistence triggers clean rollback
    and leaves no corrupted, active, or orphan records in PostgreSQL.
    """
    # Count documents before failure
    count_before = pg_session.execute(select(func.count(Document.id))).scalar()

    # Monkeypatch session.commit to simulate database constraint or connection failure
    def mock_commit_failure():
        raise RuntimeError("Simulated database disk or network failure during commit")

    monkeypatch.setattr(pg_session, "commit", mock_commit_failure)

    response = client.post(
        "/api/documents/upload",
        data={
            "business_id": "biz_auraskin",
            "document_type": "pricing",
            "title": "Failed Ingestion Rollback Test",
        },
        files={"file": ("fail.txt", b"Valid text that will fail during DB commit", "text/plain")},
    )
    # Returns 422 or 500 error cleanly
    assert response.status_code in [422, 500]

    # Verify document count in PostgreSQL remains strictly unchanged
    count_after = pg_session.execute(select(func.count(Document.id))).scalar()
    assert count_after == count_before

