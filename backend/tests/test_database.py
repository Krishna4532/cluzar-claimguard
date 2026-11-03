import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    Business,
    Document,
    DocumentChunk,
    Embedding,
    StructuredFact,
    Draft,
    Claim,
    Verification,
    VerificationEvidence,
    HumanReview,
)


@pytest.fixture(scope="module")
def db_session():
    """Provides an isolated in-memory SQLite database session for unit testing models."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


def test_metadata_tables_registered():
    """Verify all 10 tables are properly registered on Declarative Base."""
    expected_tables = {
        "businesses",
        "documents",
        "drafts",
        "claims",
        "document_chunks",
        "structured_facts",
        "embeddings",
        "verifications",
        "human_reviews",
        "verification_evidence",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), f"Missing tables: {expected_tables - actual_tables}"


def test_business_and_document_creation(db_session):
    """Test creating a business and associated document with content hash and versioning."""
    biz = Business(
        business_id="biz_auraskin_test",
        name="AuraSkin Test",
        industry="Skincare",
        currency="INR",
        timezone="Asia/Kolkata",
    )
    db_session.add(biz)
    db_session.commit()
    assert biz.id is not None

    doc = Document(
        document_id="doc_as_test_01",
        business_id=biz.id,
        document_type="product_catalog",
        title="Catalog 2026",
        content="Radiance Glow Vitamin C Serum: INR 899.",
        content_hash="abc123hash",
        version=1,
        status="active",
    )
    db_session.add(doc)
    db_session.commit()
    assert doc.id is not None
    assert doc.business.business_id == "biz_auraskin_test"


def test_chunk_and_embedding_lifecycle(db_session):
    """Test chunking with character offsets and vector embedding linkage."""
    biz = db_session.execute(select(Business).filter_by(business_id="biz_auraskin_test")).scalar_one()
    doc = db_session.execute(select(Document).filter_by(document_id="doc_as_test_01")).scalar_one()

    chunk = DocumentChunk(
        document_id=doc.id,
        chunk_index=0,
        content="Radiance Glow Vitamin C Serum: INR 899.",
        start_char=0,
        end_char=40,
        chunk_metadata={"section": "pricing", "product": "Vitamin C Serum"},
    )
    db_session.add(chunk)
    db_session.commit()
    assert chunk.id is not None

    # Dummy 384-dimensional vector for testing
    dummy_vec = [0.05] * 384
    emb = Embedding(
        chunk_id=chunk.id,
        embedding=dummy_vec,
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    )
    db_session.add(emb)
    db_session.commit()
    assert emb.id is not None
    assert emb.chunk.chunk_index == 0


def test_structured_fact_storage(db_session):
    """Test structured factual extraction storage with JSON conditions."""
    biz = db_session.execute(select(Business).filter_by(business_id="biz_auraskin_test")).scalar_one()
    doc = db_session.execute(select(Document).filter_by(document_id="doc_as_test_01")).scalar_one()

    fact = StructuredFact(
        business_id=biz.id,
        document_id=doc.id,
        fact_type="price",
        subject="Radiance Glow Vitamin C Serum",
        predicate="approved_price",
        value={"amount": 899, "currency": "INR"},
        conditions={"min_order_value": 0},
    )
    db_session.add(fact)
    db_session.commit()
    assert fact.id is not None
    assert fact.value["amount"] == 899


def test_draft_claim_verification_pipeline_entities(db_session):
    """Test end-to-end pipeline entities: Draft -> Claim -> Verification -> Evidence & Human Review."""
    biz = db_session.execute(select(Business).filter_by(business_id="biz_auraskin_test")).scalar_one()
    chunk = db_session.execute(select(DocumentChunk).filter_by(chunk_index=0)).scalar_one()

    # 1. Draft
    draft = Draft(
        business_id=biz.id,
        content="Our Vitamin C Serum is available for INR 899.",
        status="pending",
    )
    db_session.add(draft)
    db_session.commit()
    assert draft.id is not None

    # 2. Claim
    claim = Claim(
        draft_id=draft.id,
        claim_text="available for INR 899",
        claim_type="price",
        start_char=24,
        end_char=45,
    )
    db_session.add(claim)
    db_session.commit()
    assert claim.id is not None

    # 3. Verification
    verification = Verification(
        claim_id=claim.id,
        verdict="supported",
        rationale="Price of INR 899 matches catalog specifications.",
        confidence=0.98,
    )
    db_session.add(verification)
    db_session.commit()
    assert verification.id is not None

    # 4. Evidence
    evidence = VerificationEvidence(
        verification_id=verification.id,
        chunk_id=chunk.id,
        relevance_score=0.95,
        evidence_text="Radiance Glow Vitamin C Serum: INR 899.",
    )
    db_session.add(evidence)
    db_session.commit()
    assert evidence.id is not None

    # 5. Human Review
    review = HumanReview(
        verification_id=verification.id,
        reviewer_decision="approved",
        reviewer_notes="Verified against Q4 price list.",
    )
    db_session.add(review)
    db_session.commit()
    assert review.id is not None
    assert review.verification.verdict == "supported"


def test_cascade_deletion(db_session):
    """Verify that deleting a business cascades properly to clean up child documents and drafts."""
    biz = Business(
        business_id="biz_to_delete",
        name="Temporary Biz",
        industry="Test",
    )
    db_session.add(biz)
    db_session.commit()

    doc = Document(
        document_id="doc_temp",
        business_id=biz.id,
        document_type="test",
        title="Test Doc",
        content="Content",
        content_hash="hash1",
    )
    db_session.add(doc)
    db_session.commit()

    doc_id = doc.id
    db_session.delete(biz)
    db_session.commit()

    deleted_doc = db_session.execute(select(Document).filter_by(id=doc_id)).scalar_one_or_none()
    assert deleted_doc is None

