"""Validate uploaded media by content and store it by hash under the media directory."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

IMAGE_LIMIT = 20 * 1024 * 1024
VIDEO_LIMIT = 100 * 1024 * 1024
TOTAL_LIMIT = 100 * 1024 * 1024
MAX_FILES = 4
EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
}


class MediaRejected(ValueError):
    pass


@dataclass(frozen=True)
class StoredMedia:
    kind: str
    mime_type: str
    size_bytes: int
    sha256: str
    filename: str
    storage_name: str


def sniff(data: bytes) -> tuple[str, str] | None:
    """Return (kind, mime type) from file signatures; declared types are not trusted."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image", "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image", "image/png"
    if data[:6] in {b"GIF87a", b"GIF89a"}:
        return "image", "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image", "image/webp"
    if data[4:8] == b"ftyp":
        return "video", "video/mp4"
    return None


def validate(files: list[tuple[str, bytes]]) -> list[tuple[str, str, str, bytes]]:
    """Check count, type and size limits; returns (filename, kind, mime type, data)."""
    if len(files) > MAX_FILES:
        raise MediaRejected(f"Attach up to {MAX_FILES} files.")
    if sum(len(data) for _, data in files) > TOTAL_LIMIT:
        raise MediaRejected("Attached files exceed 100 MB in total.")
    checked = []
    for filename, data in files:
        detected = sniff(data)
        if detected is None:
            raise MediaRejected(f"{filename}: use JPEG, PNG, GIF, WebP or MP4.")
        kind, mime_type = detected
        limit = IMAGE_LIMIT if kind == "image" else VIDEO_LIMIT
        if not data or len(data) > limit:
            raise MediaRejected(f"{filename}: file is empty or larger than {limit // 2**20} MB.")
        checked.append((filename, kind, mime_type, data))
    return checked


def store(media_dir: Path, filename: str, kind: str, mime_type: str, data: bytes) -> StoredMedia:
    digest = hashlib.sha256(data).hexdigest()
    storage_name = digest + EXTENSIONS[mime_type]
    media_dir.mkdir(parents=True, exist_ok=True)
    target = media_dir / storage_name
    if not target.exists():
        temporary = target.with_suffix(target.suffix + ".part")
        temporary.write_bytes(data)
        temporary.replace(target)
    # Keep only a short, path-free display name.
    display = Path(filename or "upload").name[:200]
    return StoredMedia(kind, mime_type, len(data), digest, display, storage_name)
