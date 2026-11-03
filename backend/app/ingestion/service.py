import os
import uuid
from typing import Tuple, Optional
from fastapi import UploadFile
from sqlalchemy import select, and_, func
from sqlalchemy.orm import Session

from app.db.models.business import Business
from app.db.models.document import Document
from app.ingestion.exceptions import (
    BusinessNotFoundError,
    DocumentValidationError,
    DocumentExtractionError,
)
from app.ingestion.hashing import read_and_hash_upload
from app.ingestion.loaders import PDFDocumentLoader, TextDocumentLoader
from app.ingestion.normalizer import normalize_text


class DocumentIngestionService:
    def __init__(self, db: Session):
        self.db = db
        self.pdf_loader = PDFDocumentLoader()
        self.txt_loader = TextDocumentLoader()

    def validate_business(self, business_id_str: str) -> Business:
        """Ensures the referenced business exists in the database."""
        stmt = select(Business).where(Business.business_id == business_id_str)
        biz = self.db.execute(stmt).scalar_one_or_none()
        if not biz:
            raise BusinessNotFoundError(business_id_str)
        return biz

    async def ingest_document(
        self,
        business_id_str: str,
        document_type: str,
        title: str,
        upload_file: UploadFile,
    ) -> Tuple[Document, bool]:
        """
        Coordinates full document ingestion pipeline:
        1. Validates business.
        2. Validates file extension and mime/header.
        3. Streams bytes, enforcing 10MB limit and calculating SHA-256.
        4. Detects duplicates within the same business tenant.
        5. Handles versioning if the document has changed.
        6. Extracts and validates text content.
        7. Persists transactionally.

        Returns:
            Tuple[Document, is_duplicate: bool]
        """
        # 1. Validate business ownership
        business = self.validate_business(business_id_str)

        # 2. Validate title and document_type inputs
        title = title.strip()
        document_type = document_type.strip().lower()
        if not title:
            raise DocumentValidationError("Document title cannot be empty.")
        if not document_type:
            raise DocumentValidationError("Document type cannot be empty.")

        filename = upload_file.filename or ""
        _, ext = os.path.splitext(filename)
        ext = ext.lower()

        if ext not in [".pdf", ".txt"]:
            raise DocumentValidationError(
                f"Unsupported file extension '{ext}'. Only .pdf and .txt are accepted."
            )
        file_type = ext.lstrip(".")

        # 3. Stream read and SHA-256 hash
        content_bytes, file_hash = await read_and_hash_upload(upload_file)

        # 4. Duplicate Detection (scoped to this business!)
        # Rule: Same business + identical file hash -> return existing active document
        stmt_dup = select(Document).where(
            and_(
                Document.business_id == business.id,
                Document.content_hash == file_hash,
                Document.status == "active",
            )
        )
        existing_dup = self.db.execute(stmt_dup).scalar_one_or_none()
        if existing_dup:
            return existing_dup, True

        # 5. Extract text page-by-page
        if file_type == "pdf":
            raw_text, metadata = self.pdf_loader.load(content_bytes, filename)
        else:
            raw_text, metadata = self.txt_loader.load(content_bytes, filename)

        # 6. Logical Document Identity & Versioning
        # Identity is defined as (business_id + title + document_type)
        stmt_versions = select(Document).where(
            and_(
                Document.business_id == business.id,
                Document.title == title,
                Document.document_type == document_type,
            )
        ).order_by(Document.version.desc())
        existing_versions = self.db.execute(stmt_versions).scalars().all()

        if existing_versions:
            # New revision of an existing document
            highest_version = existing_versions[0].version
            new_version = highest_version + 1
            # Mark previous active version as superseded
            for doc in existing_versions:
                if doc.status == "active":
                    doc.status = "superseded"
        else:
            new_version = 1

        # 7. Generate unique document ID
        biz_slug = business.business_id.replace("biz_", "")
        unique_id = f"doc_{biz_slug}_{uuid.uuid4().hex[:8]}"

        # 8. Persist inside transaction
        try:
            document = Document(
                document_id=unique_id,
                business_id=business.id,
                document_type=document_type,
                title=title,
                file_type=file_type,
                content=raw_text,
                content_hash=file_hash,
                version=new_version,
                status="active",
                doc_metadata=metadata,
            )
            self.db.add(document)
            self.db.commit()
            self.db.refresh(document)
            return document, False

        except Exception as e:
            self.db.rollback()
            raise DocumentExtractionError(f"Failed to persist document transaction: {str(e)}")

