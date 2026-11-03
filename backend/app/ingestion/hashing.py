import hashlib
from typing import Tuple, BinaryIO
from fastapi import UploadFile
from app.ingestion.exceptions import DocumentSizeExceededError, DocumentValidationError

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
CHUNK_SIZE_BYTES = 64 * 1024  # 64 KB


async def read_and_hash_upload(upload_file: UploadFile) -> Tuple[bytes, str]:
    """
    Reads an uploaded file in chunks, calculating its SHA-256 digest on the fly
    while enforcing the 10 MB ceiling before unbounded memory allocation can occur.

    Returns:
        Tuple[bytes, sha256_hex_digest]
    Raises:
        DocumentSizeExceededError: If file exceeds 10 MB.
        DocumentValidationError: If file is empty (0 bytes).
    """
    hasher = hashlib.sha256()
    total_bytes = 0
    chunks = []

    # Reset file pointer to beginning if previously read
    await upload_file.seek(0)

    while True:
        chunk = await upload_file.read(CHUNK_SIZE_BYTES)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > MAX_FILE_SIZE_BYTES:
            raise DocumentSizeExceededError(
                f"Uploaded file exceeds the maximum allowed size of 10 MB (received > {total_bytes} bytes)."
            )
        hasher.update(chunk)
        chunks.append(chunk)

    if total_bytes == 0:
        raise DocumentValidationError("Uploaded file is empty (0 bytes).")

    content_bytes = b"".join(chunks)
    sha256_hash = hasher.hexdigest()
    return content_bytes, sha256_hash

