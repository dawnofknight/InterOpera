from __future__ import annotations

import re
from decimal import Decimal

from interopera.domain.models import HoldingRecord, Provenance, SourceChunk, SourceDocument
from interopera.config.models import FirmConfig
from interopera.canonical import sha256_bytes
from datetime import datetime, timezone
from interopera.graph.schema import Edge, Node, PropertyGraph


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


ASSET_CLASSES = {
    "Singapore Government Securities": "sgs",
    "MAS Bills": "mas_bills",
    "Investment Grade Corporate Bonds": "ig_corporate",
    "High Yield Bonds": "high_yield",
    "Foreign Currency Bonds": "foreign_bonds",
    "Structured Credit": "structured_credit",
    "Cash & Cash Equivalents": "cash",
}

POLICY_RULES = (
    ("allocation_sgs", "allocation:sgs", "range", "0.20", "0.60", "nav_ratio", 1),
    ("allocation_mas_bills", "allocation:mas_bills", "range", "0", "0.40", "nav_ratio", 1),
    ("allocation_ig_corporate", "allocation:ig_corporate", "range", "0.10", "0.50", "nav_ratio", 1),
    ("allocation_high_yield", "allocation:high_yield", "range", "0", "0.15", "nav_ratio", 1),
    ("allocation_foreign_bonds", "allocation:foreign_bonds", "range", "0", "0.20", "nav_ratio", 2),
    ("allocation_structured_credit", "allocation:structured_credit", "range", "0", "0.10", "nav_ratio", 2),
    ("allocation_cash", "allocation:cash", "min", "0.05", None, "nav_ratio", 2),
    ("aggregate_non_ig_exposure", "aggregate:non_ig", "max", None, "0.20", "nav_ratio", 2),
    ("largest_single_corporate_issuer", "concentration:corporate", "max", None, "0.08", "nav_ratio", 2),
    ("largest_gre_issuer", "concentration:gre", "max", None, "0.12", "nav_ratio", 2),
    ("liquid_assets_ratio", "liquidity:normal", "min", "0.25", None, "nav_ratio", 2),
    ("portfolio_modified_duration", "metric:portfolio_duration", "range", "2.0", "6.5", "years", 2),
    ("portfolio_dv01", "metric:portfolio_dv01", "max", None, "85000", "sgd_per_bp", 2),
)


def build_graph(
    documents: tuple[SourceDocument, ...],
    guideline_chunks: tuple[tuple[SourceChunk, Provenance], ...],
    holdings: tuple[HoldingRecord, ...],
) -> PropertyGraph:
    nodes: dict[str, Node] = {}
    edges: dict[str, Edge] = {}

    def add_node(identifier: str, label: str, properties: dict[str, object], provenance: tuple[Provenance, ...]) -> None:
        nodes.setdefault(identifier, Node(id=identifier, label=label, properties=properties, provenance=provenance))

    def add_edge(identifier: str, label: str, source: str, target: str, provenance: tuple[Provenance, ...]) -> None:
        edges[identifier] = Edge(id=identifier, label=label, source=source, target=target, provenance=provenance)

    page_prov: dict[int, Provenance] = {}
    for chunk, provenance in guideline_chunks:
        page_prov.setdefault(chunk.page or 1, provenance)
        add_node(chunk.id, "SourceChunk", chunk.model_dump(mode="python"), (provenance,))
        add_edge(f"edge:{chunk.id}:part_of", "PART_OF", chunk.id, chunk.source_document_id, (provenance,))
    for document in documents:
        relevant = next((p for _, p in guideline_chunks if p.source_document_id == document.id), None)
        if relevant is None:
            relevant = holdings[0].provenance
        add_node(document.id, "SourceDocument", document.model_dump(mode="python"), (relevant,))

    portfolio_prov = holdings[0].provenance
    add_node("portfolio:meridian_fixed_income", "Portfolio", {"name": "Meridian Fixed Income Fund", "currency": "SGD"}, (portfolio_prov,))
    for record in holdings:
        prov = (record.provenance,)
        chunk_id = record.provenance.chunk_id
        add_node(chunk_id, "SourceChunk", {
            "id": chunk_id, "source_document_id": record.provenance.source_document_id,
            "page": None, "row_number": record.provenance.row_number, "text": record.instrument_id,
            "normalized_text_sha256": record.provenance.chunk_sha256, "bbox": None,
        }, prov)
        add_edge(f"edge:{chunk_id}:part_of", "PART_OF", chunk_id, record.provenance.source_document_id, prov)
        position_id = f"position:{record.instrument_id}"
        add_node(position_id, "Position", record.model_dump(mode="python", exclude={"provenance"}), prov)
        add_edge(f"edge:portfolio:{record.instrument_id}", "HOLDS", "portfolio:meridian_fixed_income", position_id, prov)
        add_edge(f"edge:{record.instrument_id}:source", "DERIVED_FROM", position_id, chunk_id, prov)
        class_key = ASSET_CLASSES.get(record.asset_class)
        if class_key is None:
            raise ValueError(f"Unknown asset class {record.asset_class}")
        class_id = f"asset_class:{class_key}"
        add_node(class_id, "AssetClass", {"name": record.asset_class, "key": class_key}, prov)
        add_edge(f"edge:{record.instrument_id}:class", "BELONGS_TO", position_id, class_id, prov)
        issuer_id = f"issuer:{slug(record.issuer_name)}"
        add_node(issuer_id, "Issuer", {"name": record.issuer_name, "issuer_type": record.issuer_type}, prov)
        add_edge(f"edge:{record.instrument_id}:issuer", "ISSUED_BY", position_id, issuer_id, prov)
        if record.parent_issuer:
            parent_id = f"parent:{slug(record.parent_issuer)}"
            add_node(parent_id, "ParentIssuer", {"name": record.parent_issuer}, prov)
            add_edge(f"edge:{issuer_id}:parent", "ROLLS_UP_TO", issuer_id, parent_id, prov)

    # Policy memberships are explicit graph facts.
    p2 = page_prov.get(2, next(iter(page_prov.values())))
    add_node("aggregate:non_ig", "Aggregate", {"name": "Aggregate non-IG"}, (p2,))
    for key in ("high_yield", "structured_credit"):
        add_edge(f"edge:asset_class:{key}:non_ig", "CONTRIBUTES_TO", f"asset_class:{key}", "aggregate:non_ig", (p2,))
    add_node("liquidity:normal", "LiquidityBucket", {"name": "Normal liquidity", "condition": "normal"}, (p2,))
    for key in ("sgs", "mas_bills", "cash"):
        add_edge(f"edge:asset_class:{key}:liquid", "INCLUDED_IN", f"asset_class:{key}", "liquidity:normal", (p2,))

    for figure_id, subject_id, kind, minimum, maximum, unit, page in POLICY_RULES:
        provenance = page_prov.get(page, p2)
        if subject_id not in nodes:
            label = "Metric" if subject_id.startswith("metric:") else ("Aggregate" if subject_id.startswith("aggregate:") else "Metric")
            add_node(subject_id, label, {"name": figure_id}, (provenance,))
        limit_id = f"limit:{figure_id}"
        add_node(limit_id, "LimitRule", {
            "metric_id": subject_id, "kind": kind, "min_value": minimum,
            "max_value": maximum, "unit": unit,
        }, (provenance,))
        add_edge(f"edge:{subject_id}:limit", "SUBJECT_TO", subject_id, limit_id, (provenance,))
        add_edge(f"edge:{limit_id}:source", "DERIVED_FROM", limit_id, provenance.chunk_id, (provenance,))

    # Required duration breach route.
    add_node("action:pm_notification_within_1h", "BreachAction", {"text": "Notify PM within one hour"}, (p2,))
    add_node("owner:portfolio_manager", "Owner", {"name": "Portfolio Manager"}, (p2,))
    add_edge("edge:limit:duration:action", "HAS_BREACH_ACTION", "limit:portfolio_modified_duration", "action:pm_notification_within_1h", (p2,))
    add_edge("edge:action:duration:owner", "NOTIFIES", "action:pm_notification_within_1h", "owner:portfolio_manager", (p2,))
    add_edge("edge:action:duration:source", "DERIVED_FROM", "action:pm_notification_within_1h", p2.chunk_id, (p2,))
    return PropertyGraph(nodes=tuple(sorted(nodes.values(), key=lambda n: n.id)), edges=tuple(sorted(edges.values(), key=lambda e: e.id)))


def add_config_graph(graph: PropertyGraph, config: FirmConfig, document: SourceDocument, text: str) -> PropertyGraph:
    """Materialize generic method choices so calculations have method lineage."""
    text_hash = sha256_bytes(" ".join(text.split()).encode())
    chunk_id = "chunk_" + sha256_bytes(f"{document.sha256}:1:{' '.join(text.split())}".encode())[:16]
    provenance = Provenance(
        source_document_id=document.id, source_doc=document.filename, source_sha256=document.sha256,
        line_start=1, line_end=len(text.splitlines()), chunk_id=chunk_id, chunk_sha256=text_hash,
        ingestion_time=datetime.now(timezone.utc), extraction_method="deterministic",
        extraction_confidence=Decimal("1"), passage_summary=f"Validated configuration for {config.display_name}",
    )
    nodes = list(graph.nodes)
    edges = list(graph.edges)
    nodes.append(Node(id=document.id, label="SourceDocument", properties=document.model_dump(mode="python"), provenance=(provenance,)))
    nodes.append(Node(id=chunk_id, label="SourceChunk", properties={
        "id": chunk_id, "source_document_id": document.id, "page": None, "row_number": None,
        "text": text, "normalized_text_sha256": text_hash, "bbox": None,
    }, provenance=(provenance,)))
    edges.append(Edge(id=f"edge:{chunk_id}:part_of", label="PART_OF", source=chunk_id, target=document.id, provenance=(provenance,)))
    strategies = {
        "aggregate_non_ig": config.aggregate_non_ig.model_dump(mode="python"),
        "corporate_grouping": config.concentration.corporate.model_dump(mode="python"),
        "gre_grouping": config.concentration.gre.model_dump(mode="python"),
        "liquidity": config.liquidity.model_dump(mode="python"),
        "utilization": config.utilization.model_dump(mode="python"),
        "formatting": config.value_formatting.model_dump(mode="python"),
    }
    for key, properties in strategies.items():
        identifier = f"method:{config.firm_id}:{key}"
        nodes.append(Node(id=identifier, label="FirmMethodRule", properties=properties, provenance=(provenance,)))
        edges.append(Edge(id=f"edge:{identifier}:source", label="DERIVED_FROM", source=identifier, target=chunk_id, provenance=(provenance,)))
    return PropertyGraph(nodes=tuple(sorted(nodes, key=lambda node: node.id)), edges=tuple(sorted(edges, key=lambda edge: edge.id)))
