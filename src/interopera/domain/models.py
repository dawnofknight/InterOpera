from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from interopera.domain.enums import LimitKind, NumericUnit, Status


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Provenance(FrozenModel):
    source_document_id: str
    source_doc: str
    source_sha256: str
    page: int | None = None
    row_number: int | None = None
    line_start: int | None = None
    line_end: int | None = None
    chunk_id: str
    chunk_sha256: str
    ingestion_time: datetime
    extraction_method: Literal["deterministic", "llm_candidate", "human_authored", "derived"]
    extraction_confidence: Decimal = Field(ge=0, le=1)
    passage_summary: str


class SourceDocument(FrozenModel):
    id: str
    filename: str
    media_type: str
    sha256: str
    size_bytes: int
    registered_at: datetime


class SourceChunk(FrozenModel):
    id: str
    source_document_id: str
    page: int | None = None
    row_number: int | None = None
    text: str
    normalized_text_sha256: str
    bbox: tuple[Decimal, Decimal, Decimal, Decimal] | None = None


class HoldingRecord(FrozenModel):
    instrument_id: str = Field(min_length=1)
    instrument_name: str
    asset_class: str
    issuer_name: str
    issuer_type: Literal["government", "corporate", "GRE", "spv", "cash"]
    parent_issuer: str | None = None
    credit_rating: str | None = None
    downgraded_from: str | None = None
    market_value_sgd: Decimal = Field(ge=0)
    modified_duration: Decimal = Field(ge=0)
    provenance: Provenance


class LimitRule(FrozenModel):
    id: str
    metric_id: str
    kind: LimitKind
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    unit: Literal["nav_ratio", "years", "sgd_per_bp"]
    exclusions: tuple[str, ...] = ()
    breach_action_ids: tuple[str, ...] = ()
    owner_ids: tuple[str, ...] = ()
    provenance: tuple[Provenance, ...]


class NumericValue(FrozenModel):
    amount: Decimal
    unit: NumericUnit


class Citation(FrozenModel):
    source_doc: str
    page: int | None = None
    row_number: int | None = None
    chunk_id: str
    passage_summary: str


class TraceStep(FrozenModel):
    ordinal: int
    from_node_id: str
    edge_id: str
    relation: str
    to_node_id: str
    provenance_refs: tuple[str, ...]


class ComputedFigure(FrozenModel):
    figure_id: str
    section: str
    metric: str
    raw_value: NumericValue | None
    display_value: str | None
    raw_limit: LimitRule
    display_limit: str
    raw_utilization: Decimal | None
    display_utilization: str
    status: Status
    material_breach: bool
    calculation_id: str
    formula_version: str = "1.0"
    config_rule_ids: tuple[str, ...]
    input_node_ids: tuple[str, ...]
    graph_path: tuple[TraceStep, ...]
    citations: tuple[Citation, ...]
    source_summary: str
    error: dict[str, str] | None = None

