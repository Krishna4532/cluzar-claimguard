from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentUploadResponse(BaseModel):
    document_id: str = Field(..., description="Unique business-scoped document identifier")
    business_id: str = Field(..., description="Tenant business string ID")
    title: str = Field(..., description="Document title")
    document_type: str = Field(..., description="Business category of document")
    file_type: str = Field(..., description="Extension/format: 'pdf' or 'txt'")
    file_hash: str = Field(..., description="SHA-256 hash of original uploaded bytes")
    version: int = Field(..., description="Document revision version number")
    status: str = Field(..., description="Document status ('active', 'superseded', etc.)")
    extracted_character_count: int = Field(..., description="Total characters of extracted text")
    created_at: datetime = Field(..., description="UTC creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class DocumentMetadataResponse(BaseModel):
    document_id: str
    business_id: str
    title: str
    document_type: str
    file_type: str
    file_hash: str
    version: int
    status: str
    extracted_character_count: int
    page_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: List[DocumentMetadataResponse]
    total: int

