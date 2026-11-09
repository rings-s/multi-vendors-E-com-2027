"""Image upload validation and storage.

* Content is validated by magic bytes, not by the client-supplied content type.
* Files are stored under random names (no user-controlled paths).
* Size is limited by ``UPLOAD_MAX_BYTES``.
"""

import uuid
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import ValidationFailed

_SIGNATURES: tuple[tuple[bytes, int, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", 0, "png"),
    (b"\xff\xd8\xff", 0, "jpg"),
    (b"WEBP", 8, "webp"),
)


def detect_image_type(head: bytes) -> str | None:
    for signature, offset, ext in _SIGNATURES:
        if head[offset : offset + len(signature)] == signature:
            if ext == "webp" and head[:4] != b"RIFF":
                continue
            return ext
    return None


def store_image(content: bytes, *, folder: str) -> str:
    settings = get_settings()
    if not content:
        raise ValidationFailed("Empty file.")
    if len(content) > settings.upload_max_bytes:
        raise ValidationFailed("File is too large.", details={"max_bytes": settings.upload_max_bytes})
    ext = detect_image_type(content[:16])
    if ext is None:
        raise ValidationFailed("Only PNG, JPEG and WebP images are allowed.")
    safe_folder = "".join(ch for ch in folder if ch.isalnum() or ch in "-_") or "misc"
    directory = Path(settings.upload_dir) / safe_folder
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    (directory / name).write_bytes(content)
    return f"{settings.media_url_prefix}/{safe_folder}/{name}"
