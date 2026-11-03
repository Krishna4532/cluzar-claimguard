import io
import pytest
from starlette.datastructures import UploadFile as StarletteUploadFile
from pypdf import PdfWriter

from app.ingestion.exceptions import (
    DocumentValidationError,
    DocumentSizeExceededError,
    DocumentExtractionError,
)
from app.ingestion.normalizer import normalize_text
from app.ingestion.hashing import read_and_hash_upload, MAX_FILE_SIZE_BYTES
from app.ingestion.loaders import TextDocumentLoader, PDFDocumentLoader


def create_minimal_pdf_bytes(text: str = "AuraSkin Product Specifications Price List 2026") -> bytes:
    """Helper creating a minimal valid PDF with an embedded Helvetica text stream."""
    stream_content = f"BT /F1 18 Tf 50 700 Td ({text}) Tj ET".encode("ascii", errors="replace")
    stream_len = len(stream_content)
    pdf_template = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length " + str(stream_len).encode("ascii") + b" >>\nstream\n"
        + stream_content + b"\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\nxref\n0 6\n"
        b"0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n350\n%%EOF"
    )
    return pdf_template


# ==========================================
# 1. Text Normalization Unit Tests
# ==========================================

def test_normalize_text_whitespace_and_paragraphs():
    raw = "  Line 1 with trailing spaces   \r\n\r\n\r\n\r\nLine 2 after quadruple newline\rLine 3  "
    result = normalize_text(raw)
    assert "Line 1 with trailing spaces" in result
    assert "\r" not in result
    assert "\n\n\n" not in result  # Collapsed into paragraph break
    assert result.endswith("Line 3")


def test_normalize_text_preserves_hinglish_and_currencies():
    raw = "Hamara Nordic Solid Sheesham Dining Table pure ₹24,999 mein 15% discount par available hai!"
    result = normalize_text(raw)
    assert result == raw
    assert "₹" in result
    assert "24,999" in result
    assert "15%" in result


# ==========================================
# 2. Hashing & Streaming Size Enforcement Tests
# ==========================================

@pytest.mark.anyio
async def test_read_and_hash_valid_upload():
    content = b"Radiance Glow Vitamin C Serum: INR 899."
    upload = StarletteUploadFile(filename="catalog.txt", file=io.BytesIO(content))
    data, sha = await read_and_hash_upload(upload)
    assert data == content
    assert len(sha) == 64  # SHA-256 hex string


@pytest.mark.anyio
async def test_read_and_hash_empty_file_rejected():
    upload = StarletteUploadFile(filename="empty.txt", file=io.BytesIO(b""))
    with pytest.raises(DocumentValidationError, match="empty"):
        await read_and_hash_upload(upload)


@pytest.mark.anyio
async def test_read_and_hash_oversized_file_rejected():
    # 10 MB + 1 byte
    oversized_data = b"X" * (MAX_FILE_SIZE_BYTES + 1024)
    upload = StarletteUploadFile(filename="huge.txt", file=io.BytesIO(oversized_data))
    with pytest.raises(DocumentSizeExceededError, match="exceeds the maximum allowed size of 10 MB"):
        await read_and_hash_upload(upload)


# ==========================================
# 3. Document Loaders Unit Tests
# ==========================================

def test_text_loader_utf8_and_bom():
    loader = TextDocumentLoader()
    # UTF-8 with BOM
    bom_content = b"\xef\xbb\xbfAuraSkin HydraDew Hyaluronic Gel Moisturizer: INR 649."
    text, meta = loader.load(bom_content, "moisturizer.txt")
    assert "HydraDew Hyaluronic Gel Moisturizer" in text
    assert meta["format"] == "txt"
    assert meta["page_count"] == 1


def test_text_loader_invalid_encoding_rejected():
    loader = TextDocumentLoader()
    # Invalid UTF-8 byte sequence
    invalid_bytes = b"\x80\x81\x82\xff"
    with pytest.raises(DocumentExtractionError, match="Failed to decode TXT file as UTF-8"):
        loader.load(invalid_bytes, "corrupt.txt")


def test_pdf_loader_valid_pdf():
    loader = PDFDocumentLoader()
    pdf_bytes = create_minimal_pdf_bytes("AuraSkin Product Specifications Price List 2026")
    text, meta = loader.load(pdf_bytes, "test.pdf")
    assert "AuraSkin Product Specifications" in text
    assert meta["format"] == "pdf"
    assert meta["page_count"] == 1
    assert len(meta["pages"]) == 1


def test_pdf_loader_malformed_header_rejected():
    loader = PDFDocumentLoader()
    malformed = b"Not a PDF file content"
    with pytest.raises(DocumentValidationError, match="valid PDF header"):
        loader.load(malformed, "fake.pdf")


def test_pdf_loader_encrypted_pdf_rejected():
    loader = PDFDocumentLoader()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret_password")
    buf = io.BytesIO()
    writer.write(buf)
    encrypted_bytes = buf.getvalue()

    with pytest.raises(DocumentExtractionError, match="Encrypted or password-protected"):
        loader.load(encrypted_bytes, "secret.pdf")


def test_pdf_loader_zero_text_pdf_rejected():
    loader = PDFDocumentLoader()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    buf = io.BytesIO()
    writer.write(buf)
    blank_bytes = buf.getvalue()

    with pytest.raises(DocumentExtractionError, match="yielded no extractable text"):
        loader.load(blank_bytes, "blank.pdf")

