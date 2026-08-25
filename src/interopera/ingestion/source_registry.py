from __future__ import annotations

import mimetypes
from datetime import datetime, timezone
from pathlib import Path

from interopera.canonical import sha256_file
from interopera.domain.models import SourceDocument
from interopera.errors import SourceError

MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".yaml": "application/yaml",
    ".yml": "application/yaml",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".md": "text/markdown",
}


def register_source(path: Path) -> SourceDocument:
    if not path.is_file():
        raise SourceError(f"Source is missing or unreadable: {path}")
    digest = sha256_file(path)
    return SourceDocument(
        id=f"doc:{path.stem}:{digest[:16]}",
        filename=path.name,
        media_type=MEDIA_TYPES.get(path.suffix.lower(), mimetypes.guess_type(path)[0] or "application/octet-stream"),
        sha256=digest,
        size_bytes=path.stat().st_size,
        registered_at=datetime.now(timezone.utc),
    )

