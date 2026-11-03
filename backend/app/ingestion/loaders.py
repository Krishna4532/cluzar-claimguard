import io
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.ingestion.exceptions import (
    DocumentValidationError,
    DocumentExtractionError,
)


class BaseDocumentLoader(ABC):
    @abstractmethod
    def load(self, content_bytes: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extracts text and page-level metadata from raw file bytes.
        Returns:
            Tuple[extracted_text, metadata_dict]
        """
        pass


class TextDocumentLoader(BaseDocumentLoader):
    """Loader for plain text documents with robust UTF-8 and UTF-8 BOM handling."""

    def load(self, content_bytes: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
        if not content_bytes:
            raise DocumentValidationError("File content is empty.")

        # Attempt decoding with UTF-8 BOM detection first
        try:
            text = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise DocumentExtractionError(
                f"Failed to decode TXT file as UTF-8. The file may contain incompatible binary characters: {e.reason}"
            )

        if not text.strip():
            raise DocumentExtractionError("TXT file contains no usable or readable text.")

        metadata = {
            "source_filename": filename,
            "format": "txt",
            "page_count": 1,
            "pages": [
                {
                    "page": 1,
                    "char_count": len(text),
                }
            ],
        }
        return text, metadata


class PDFDocumentLoader(BaseDocumentLoader):
    """Loader for PDF documents extracting text page-by-page using pypdf."""

    def load(self, content_bytes: bytes, filename: str) -> Tuple[str, Dict[str, Any]]:
        if not content_bytes:
            raise DocumentValidationError("File content is empty.")

        # Validate PDF magic header (%PDF-)
        if not content_bytes.startswith(b"%PDF-"):
            raise DocumentValidationError("File does not have a valid PDF header (%PDF-).")

        try:
            stream = io.BytesIO(content_bytes)
            reader = PdfReader(stream)

            # Check for encrypted or password-protected PDFs
            if reader.is_encrypted:
                raise DocumentExtractionError(
                    "Encrypted or password-protected PDF files cannot be processed."
                )

            page_count = len(reader.pages)
            if page_count == 0:
                raise DocumentExtractionError("PDF contains 0 pages.")

            extracted_pages: List[Dict[str, Any]] = []
            full_text_parts: List[str] = []

            for idx, page in enumerate(reader.pages, start=1):
                try:
                    page_text = page.extract_text() or ""
                except Exception as ex:
                    raise DocumentExtractionError(
                        f"Failed extracting text from PDF page {idx}: {str(ex)}"
                    )

                page_text_clean = page_text.strip()
                extracted_pages.append({
                    "page": idx,
                    "char_count": len(page_text_clean),
                })
                if page_text_clean:
                    full_text_parts.append(page_text_clean)

            combined_text = "\n\n".join(full_text_parts)
            if not combined_text.strip():
                raise DocumentExtractionError(
                    "PDF was successfully read but yielded no extractable text. Scanned or image-only PDFs without OCR are not supported."
                )

            metadata = {
                "source_filename": filename,
                "format": "pdf",
                "page_count": page_count,
                "pages": extracted_pages,
            }
            return combined_text, metadata

        except (PdfReadError, ValueError) as err:
            raise DocumentValidationError(f"Malformed or unreadable PDF document: {str(err)}")
        except DocumentExtractionError:
            raise
        except Exception as err:
            raise DocumentExtractionError(f"Unexpected error while parsing PDF: {str(err)}")

