class IngestionError(Exception):
    """Base class for all ingestion pipeline errors."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DocumentValidationError(IngestionError):
    """Raised when file format, extension, or content validation fails."""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class DocumentSizeExceededError(IngestionError):
    """Raised when uploaded file exceeds the 10 MB limit."""
    def __init__(self, message: str = "Uploaded file exceeds the maximum allowed size of 10 MB."):
        super().__init__(message, status_code=413)


class BusinessNotFoundError(IngestionError):
    """Raised when the requested business_id does not exist in the database."""
    def __init__(self, business_id: str):
        super().__init__(f"Business with id '{business_id}' does not exist.", status_code=404)


class DocumentNotFoundError(IngestionError):
    """Raised when a requested document is not found."""
    def __init__(self, document_id: str):
        super().__init__(f"Document '{document_id}' not found.", status_code=404)


class DuplicateDocumentError(IngestionError):
    """Raised or referenced when identical file has already been ingested for the business."""
    def __init__(self, document_id: str, message: str = "An identical document has already been ingested for this business."):
        super().__init__(message, status_code=409)
        self.document_id = document_id


class DocumentExtractionError(IngestionError):
    """Raised when text cannot be extracted from a PDF/TXT or yields no usable text."""
    def __init__(self, message: str):
        super().__init__(message, status_code=422)

