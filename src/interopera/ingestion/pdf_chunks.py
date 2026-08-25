from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from interopera.canonical import sha256_bytes
from interopera.domain.models import Provenance, SourceChunk, SourceDocument
from interopera.errors import SourceError


def chunk_pdf(path: Path, document: SourceDocument) -> tuple[tuple[SourceChunk, Provenance], ...]:
    try:
        import fitz
    except ImportError as exc:
        raise SourceError("PyMuPDF is required to ingest guideline PDFs") from exc
    chunks: list[tuple[SourceChunk, Provenance]] = []
    try:
        pdf = fitz.open(path)
        for page_index, page in enumerate(pdf, start=1):
            blocks = sorted(page.get_text("blocks"), key=lambda block: (block[1], block[0]))
            for block in blocks:
                text = " ".join(str(block[4]).split())
                if not text:
                    continue
                text_hash = sha256_bytes(text.encode())
                chunk_id = "chunk_" + sha256_bytes(f"{document.sha256}:{page_index}:{text}".encode())[:16]
                chunk = SourceChunk(
                    id=chunk_id,
                    source_document_id=document.id,
                    page=page_index,
                    text=text,
                    normalized_text_sha256=text_hash,
                    bbox=tuple(Decimal(str(value)) for value in block[:4]),
                )
                provenance = Provenance(
                    source_document_id=document.id, source_doc=document.filename,
                    source_sha256=document.sha256, page=page_index, chunk_id=chunk_id,
                    chunk_sha256=text_hash, ingestion_time=datetime.now(timezone.utc),
                    extraction_method="deterministic", extraction_confidence=Decimal("1"),
                    passage_summary=text[:120],
                )
                chunks.append((chunk, provenance))
        pdf.close()
    except Exception as exc:
        raise SourceError(f"Unable to parse PDF {path}: {exc}") from exc
    if not chunks:
        raise SourceError(f"PDF contains no extractable text: {path}")
    return tuple(chunks)

