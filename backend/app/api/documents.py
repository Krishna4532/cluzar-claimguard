from typing import List
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.business import Business
from app.db.models.chunk import DocumentChunk
from app.db.models.document import Document
from app.db.models.embedding import Embedding
from app.ingestion.exceptions import IngestionError, BusinessNotFoundError, DocumentNotFoundError
from app.ingestion.service import DocumentIngestionService
from app.schemas.document import (
    DocumentUploadResponse,
    DocumentMetadataResponse,
    DocumentListResponse,
)
from app.schemas.processing import ProcessingResponse, ChunkItem, ChunksListResponse
from app.services.processing import DocumentProcessingService

router = APIRouter(prefix="/api", tags=["Documents"])


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a business source document (PDF/TXT)",
)
async def upload_document(
    business_id: str = Form(..., description="Business identifier (e.g. 'biz_auraskin')"),
    document_type: str = Form(..., description="Category (e.g. 'product_catalog', 'pricing', 'policy')"),
    title: str = Form(..., description="Human-readable title"),
    file: UploadFile = File(..., description="PDF or TXT file (max 10MB)"),
    db: Session = Depends(get_db),
):
    service = DocumentIngestionService(db)
    try:
        doc, is_duplicate = await service.ingest_document(
            business_id_str=business_id,
            document_type=document_type,
            title=title,
            upload_file=file,
        )

        return DocumentUploadResponse(
            document_id=doc.document_id,
            business_id=business_id,
            title=doc.title,
            document_type=doc.document_type,
            file_type=doc.file_type,
            file_hash=doc.content_hash,
            version=doc.version,
            status=doc.status,
            extracted_character_count=len(doc.content),
            created_at=doc.created_at,
        )

    except IngestionError as err:
        raise HTTPException(status_code=err.status_code, detail=err.message)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the document upload.",
        )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentMetadataResponse,
    summary="Get document metadata by document ID",
)
def get_document_metadata(
    document_id: str,
    db: Session = Depends(get_db),
):
    stmt = (
        select(Document, Business.business_id)
        .join(Business, Document.business_id == Business.id)
        .where(Document.document_id == document_id)
    )
    result = db.execute(stmt).first()
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Document '{document_id}' not found.")

    doc, biz_str_id = result
    page_count = doc.doc_metadata.get("page_count", 1) if isinstance(doc.doc_metadata, dict) else 1

    return DocumentMetadataResponse(
        document_id=doc.document_id,
        business_id=biz_str_id,
        title=doc.title,
        document_type=doc.document_type,
        file_type=doc.file_type,
        file_hash=doc.content_hash,
        version=doc.version,
        status=doc.status,
        extracted_character_count=len(doc.content),
        page_count=page_count,
        created_at=doc.created_at,
    )


@router.get(
    "/businesses/{business_id}/documents",
    response_model=DocumentListResponse,
    summary="List all documents belonging to a business tenant",
)
def list_business_documents(
    business_id: str,
    db: Session = Depends(get_db),
):
    stmt_biz = select(Business).where(Business.business_id == business_id)
    biz = db.execute(stmt_biz).scalar_one_or_none()
    if not biz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business with id '{business_id}' does not exist.",
        )

    stmt_docs = (
        select(Document)
        .where(Document.business_id == biz.id)
        .order_by(Document.created_at.desc())
    )
    docs = db.execute(stmt_docs).scalars().all()

    items = []
    for doc in docs:
        page_count = doc.doc_metadata.get("page_count", 1) if isinstance(doc.doc_metadata, dict) else 1
        items.append(
            DocumentMetadataResponse(
                document_id=doc.document_id,
                business_id=business_id,
                title=doc.title,
                document_type=doc.document_type,
                file_type=doc.file_type,
                file_hash=doc.content_hash,
                version=doc.version,
                status=doc.status,
                extracted_character_count=len(doc.content),
                page_count=page_count,
                created_at=doc.created_at,
            )
        )

    return DocumentListResponse(items=items, total=len(items))


# ─────────────────────────────────────────────────────────────────────────────
# Milestone 4: Document Processing (chunking + embedding)
# ─────────────────────────────────────────────────────────────────────────────


@router.post(
    "/documents/{document_id}/process",
    response_model=ProcessingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Chunk and embed an ingested document (idempotent)",
)
def process_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Trigger the chunking + vector embedding pipeline for a previously-uploaded
    document.  Safe to call multiple times — if chunks already exist, returns
    ``processing_status="already_processed"`` with a 200 response instead of 201.
    """
    from app.ingestion.exceptions import DocumentExtractionError

    service = DocumentProcessingService(db)
    try:
        result = service.process_document(document_id)
    except DocumentNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err.message)
    except DocumentExtractionError as err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err.message)
    except IngestionError as err:
        raise HTTPException(status_code=err.status_code, detail=err.message)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during document processing.",
        )

    # Return 200 for idempotent repeat calls, 201 for first-time processing
    if result.processing_status == "already_processed":
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=ProcessingResponse(**result.__dict__).model_dump(),
        )

    return ProcessingResponse(**result.__dict__)


@router.get(
    "/documents/{document_id}/chunks",
    response_model=ChunksListResponse,
    summary="List all chunks (with embedding presence) for a document",
)
def list_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
):
    """
    Return metadata for every DocumentChunk belonging to *document_id*,
    including whether each chunk has a corresponding Embedding row.
    The chunk content itself is intentionally excluded to keep payloads small.
    """
    # Verify document exists
    doc_stmt = select(Document).where(Document.document_id == document_id)
    doc = db.execute(doc_stmt).scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    # Fetch all chunks ordered by index
    chunk_stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == doc.id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = db.execute(chunk_stmt).scalars().all()

    # Collect chunk IDs that have at least one Embedding
    if chunks:
        chunk_ids = [c.id for c in chunks]
        emb_stmt = select(Embedding.chunk_id).where(Embedding.chunk_id.in_(chunk_ids))
        embedded_ids = set(db.execute(emb_stmt).scalars().all())
    else:
        embedded_ids = set()

    items = [
        ChunkItem(
            chunk_id=c.id,
            chunk_index=c.chunk_index,
            char_count=len(c.content),
            start_char=c.start_char,
            end_char=c.end_char,
            has_embedding=c.id in embedded_ids,
            metadata=c.chunk_metadata if isinstance(c.chunk_metadata, dict) else {},
        )
        for c in chunks
    ]

    return ChunksListResponse(
        document_id=document_id,
        total_chunks=len(items),
        items=items,
    )

