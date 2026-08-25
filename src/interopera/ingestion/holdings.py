from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import ValidationError

from interopera.canonical import sha256_bytes
from interopera.domain.models import HoldingRecord, Provenance, SourceDocument
from interopera.domain.rating_scale import validate_rating
from interopera.errors import HoldingValidationError

HEADERS = (
    "instrument_id", "instrument_name", "asset_class", "issuer_name", "issuer_type",
    "parent_issuer", "credit_rating", "downgraded_from", "market_value_sgd", "modified_duration",
)


def _provenance(document: SourceDocument, row_number: int, row: dict[str, str]) -> Provenance:
    normalized = "|".join(row[name].strip() for name in HEADERS)
    chunk_hash = sha256_bytes(normalized.encode())
    chunk_id = "chunk_" + sha256_bytes(f"{document.sha256}:{row_number}:{normalized}".encode())[:16]
    return Provenance(
        source_document_id=document.id,
        source_doc=document.filename,
        source_sha256=document.sha256,
        row_number=row_number,
        chunk_id=chunk_id,
        chunk_sha256=chunk_hash,
        ingestion_time=datetime.now(timezone.utc),
        extraction_method="deterministic",
        extraction_confidence=Decimal("1"),
        passage_summary=f"Holding {row['instrument_id']} source row",
    )


def load_holdings(path: Path, document: SourceDocument) -> tuple[HoldingRecord, ...]:
    records: list[HoldingRecord] = []
    seen: set[str] = set()
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != HEADERS:
                raise HoldingValidationError("CSV header does not exactly match the required schema")
            for row_number, row in enumerate(reader, start=1):
                identifier = row["instrument_id"].strip()
                if identifier in seen:
                    raise HoldingValidationError("Duplicate instrument ID", entity_id=identifier)
                seen.add(identifier)
                current = validate_rating(row["credit_rating"].strip() or None)
                prior = validate_rating(row["downgraded_from"].strip() or None)
                records.append(HoldingRecord(
                    instrument_id=identifier,
                    instrument_name=row["instrument_name"].strip(),
                    asset_class=row["asset_class"].strip(),
                    issuer_name=row["issuer_name"].strip(),
                    issuer_type=row["issuer_type"].strip(),
                    parent_issuer=row["parent_issuer"].strip() or None,
                    credit_rating=current,
                    downgraded_from=prior,
                    market_value_sgd=Decimal(row["market_value_sgd"].strip()),
                    modified_duration=Decimal(row["modified_duration"].strip()),
                    provenance=_provenance(document, row_number, row),
                ))
    except (OSError, InvalidOperation, ValidationError, KeyError) as exc:
        raise HoldingValidationError(f"Invalid holdings file: {exc}") from exc
    if not records:
        raise HoldingValidationError("Holdings file contains no positions")
    return tuple(records)

