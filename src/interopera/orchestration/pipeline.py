from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from interopera import __version__
from interopera.audit.store import AuditStore
from interopera.audit.verifier import verify_chain
from interopera.canonical import canonical_sha256, primitive, sha256_file, write_canonical
from interopera.computation.engine import ComputationEngine
from interopera.config.loader import load_config
from interopera.domain.models import ComputedFigure
from interopera.domain.models import Provenance, SourceChunk, SourceDocument
from interopera.errors import GraphApprovalRequired, ReconciliationMismatch, SourceError
from interopera.export.json_exporter import export_json
from interopera.export.xlsx_exporter import export_xlsx
from interopera.graph.builder import add_config_graph, build_graph
from interopera.graph.repository import GraphRepository
from interopera.graph.schema import PropertyGraph
from interopera.graph.serialization import graph_sha256, save_graph
from interopera.graph.validation import validate_graph
from interopera.ingestion.holdings import load_holdings
from interopera.ingestion.pdf_chunks import chunk_pdf
from interopera.ingestion.source_registry import register_source
from interopera.reconciliation.answer_key import load_answer_key
from interopera.reconciliation.reconciler import reconcile
from interopera.traceability.verifier import verify_all


def deterministic_figure_data(figures: tuple[ComputedFigure, ...]) -> list[dict[str, Any]]:
    data = primitive(figures)
    assert isinstance(data, list)

    def clean(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("ingestion_time", None)
            for child in value.values():
                clean(child)
        elif isinstance(value, list):
            for child in value:
                clean(child)
    clean(data)
    return data


def build_source_graph(guidelines: Path, holdings_path: Path) -> tuple[
    PropertyGraph, SourceDocument, SourceDocument, tuple[tuple[SourceChunk, Provenance], ...]
]:
    guideline_doc = register_source(guidelines)
    holdings_doc = register_source(holdings_path)
    chunks = chunk_pdf(guidelines, guideline_doc)
    holdings = load_holdings(holdings_path, holdings_doc)
    graph = build_graph((guideline_doc, holdings_doc), chunks, holdings)
    validate_graph(graph)
    return graph, guideline_doc, holdings_doc, chunks


def approve_graph(guidelines: Path, holdings: Path, approved_dir: Path,
                  approved_by: str = "assessment-author") -> dict[str, str]:
    graph, guideline_doc, _, chunks = build_source_graph(guidelines, holdings)
    approved_dir.mkdir(parents=True, exist_ok=True)
    digest = save_graph(approved_dir / "meridian_guidelines_v2_1.json", graph)
    chunk_projection = [primitive(chunk) for chunk, _ in chunks]
    write_canonical(approved_dir / "chunks.json", chunk_projection)
    approval = {
        "source_sha256": guideline_doc.sha256, "graph_sha256": digest,
        "schema_version": "1.0", "extractor_version": "1.0",
        "approved_by": approved_by, "approved_at": datetime.now(timezone.utc).isoformat(),
        "decision": "APPROVED",
    }
    write_canonical(approved_dir / "approval.json", approval)
    return approval


def _verify_approval(approved_dir: Path, source_hash: str, graph_hash: str) -> dict[str, Any]:
    try:
        loaded = json.loads((approved_dir / "approval.json").read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise GraphApprovalRequired("Approval record is not a JSON object")
        approval: dict[str, Any] = loaded
        committed = approved_dir / "meridian_guidelines_v2_1.json"
    except OSError as exc:
        raise GraphApprovalRequired("No committed approved graph is available") from exc
    if approval.get("decision") != "APPROVED" or approval.get("source_sha256") != source_hash:
        raise SourceError("Approved graph does not match the guidelines source hash")
    if approval.get("graph_sha256") != graph_hash or sha256_file(committed) != graph_hash:
        raise SourceError("Approved graph digest does not match reconstructed graph")
    return dict(approval)


def run_pipeline(*, firm: Path, guidelines: Path, holdings: Path, template: Path,
                 output: Path, approved_dir: Path, answer_key: Path | None = None,
                 strict_reconcile: bool = False) -> dict[str, Any]:
    config, config_hash = load_config(firm)
    graph, guideline_doc, holdings_doc, chunks = build_source_graph(guidelines, holdings)
    base_graph_hash = graph_sha256(graph)
    approval = _verify_approval(approved_dir, guideline_doc.sha256, base_graph_hash)
    config_doc = register_source(firm)
    graph = add_config_graph(graph, config, config_doc, firm.read_text(encoding="utf-8"))
    validate_graph(graph)
    inputs = {"guidelines": guideline_doc.sha256, "holdings": holdings_doc.sha256,
              "template": sha256_file(template)}
    run_id = "sha256:" + canonical_sha256({"inputs": inputs, "config": config_hash,
        "graph": base_graph_hash, "software": __version__, "formula": "1.0"})
    run_dir = output / run_id.removeprefix("sha256:")
    run_dir.mkdir(parents=True, exist_ok=True)
    audit = AuditStore(output / "audit" / "audit.sqlite3")
    started_at = datetime.now(timezone.utc).isoformat()
    audit.append(run_id, "RUN_STARTED", {"software_version": __version__, "formula_version": "1.0", "schema_version": "1.0"})
    try:
        for document in (guideline_doc, holdings_doc, config_doc):
            audit.append(run_id, "SOURCE_REGISTERED", {"filename": document.filename, "sha256": document.sha256,
                "media_type": document.media_type, "size_bytes": document.size_bytes})
        audit.append(run_id, "SOURCE_CHUNKED", {"source_sha256": guideline_doc.sha256,
            "chunk_ids": [chunk.id for chunk, _ in chunks], "algorithm_version": "1.0"})
        audit.append(run_id, "GRAPH_VALIDATION_COMPLETED", {"graph_sha256": base_graph_hash, "errors": []})
        audit.append(run_id, "GRAPH_APPROVAL_REUSED", {"source_sha256": guideline_doc.sha256,
            "graph_sha256": base_graph_hash, "approved_by": approval["approved_by"]})
        audit.append(run_id, "HOLDINGS_INGESTED", {"source_sha256": holdings_doc.sha256,
            "row_count": len(GraphRepository(graph).portfolio_positions())})
        audit.append(run_id, "CONFIG_LOADED", {"firm_id": config.firm_id, "config_sha256": config_hash, "schema_version": config.schema_version})
        repository = GraphRepository(graph)
        figures = ComputationEngine(repository, config).compute()
        figure_data = deterministic_figure_data(figures)
        figures_hash = export_json(run_dir / "computed_figures.json", figure_data)
        for figure in figures:
            audit.append(run_id, "FIGURE_COMPUTED", {"figure_id": figure.figure_id,
                "calculation_id": figure.calculation_id, "raw_value": figure.raw_value,
                "display_value": figure.display_value, "status": figure.status,
                "input_node_ids": figure.input_node_ids, "config_rule_ids": figure.config_rule_ids})
        trace_hashes = verify_all(figures, repository)
        traces = [{"figure_id": figure.figure_id, "trace_sha256": trace_hashes[figure.figure_id],
                   "graph_path": primitive(figure.graph_path), "citations": primitive(figure.citations)} for figure in figures]
        traces_hash = export_json(run_dir / "traces.json", traces)
        for figure_id, digest in trace_hashes.items():
            audit.append(run_id, "TRACE_VERIFIED", {"figure_id": figure_id, "trace_sha256": digest})
        reconciliation: dict[str, Any] = {"result": "SKIPPED", "rows": []}
        if answer_key is not None:
            # Isolation boundary: answer key is loaded only after computed figures are finalized and hashed.
            reconciliation = reconcile(figures, load_answer_key(answer_key), trace_hashes)
            reconciliation["answer_key_sha256"] = sha256_file(answer_key)
            audit.append(run_id, "RECONCILIATION_COMPLETED", reconciliation)
        export_json(run_dir / "reconciliation.json", reconciliation)
        firewall = {"result": "SKIPPED", "provider": "none"}
        export_json(run_dir / "narrative_firewall.json", firewall)
        audit.append(run_id, "NARRATIVE_FIREWALL_COMPLETED", firewall)
        if strict_reconcile and reconciliation["result"] != "PASS":
            raise ReconciliationMismatch("Strict reconciliation did not pass")
        report_path = run_dir / f"{config.firm_id}_report.xlsx"
        report_hash = export_xlsx(template, report_path, figures)
        audit.append(run_id, "REPORT_EXPORTED", {"report_sha256": report_hash,
            "template_sha256": inputs["template"], "computed_figures_sha256": figures_hash})
        audit.append(run_id, "RUN_COMPLETED", {"computed_figures_sha256": figures_hash,
            "traces_sha256": traces_hash, "report_sha256": report_hash,
            "reconciliation": reconciliation["result"]})
        chain_head = verify_chain(audit, run_id)
        manifest = {"run_id": run_id, "started_at": started_at, "software_version": __version__,
            "graph_schema_version": "1.0", "formula_version": "1.0", "firm_id": config.firm_id,
            "input_hashes": inputs, "config_sha256": config_hash,
            "approved_graph_sha256": base_graph_hash, "computed_figures_sha256": figures_hash,
            "traces_sha256": traces_hash, "report_sha256": report_hash,
            "reconciliation_summary": {"result": reconciliation["result"]},
            "traceability_summary": {"result": "PASS", "verified": len(trace_hashes)},
            "narrative_firewall_summary": firewall, "audit_chain_head": chain_head}
        export_json(run_dir / "run_manifest.json", manifest)
        return {"run_id": run_id, "run_dir": str(run_dir), "firm_id": config.firm_id,
                "reconciliation": reconciliation["result"], "figures_sha256": figures_hash,
                "traces_sha256": traces_hash, "report_sha256": report_hash}
    except Exception as exc:
        audit.append(run_id, "RUN_FAILED", {"error_type": type(exc).__name__, "message": str(exc)})
        raise
    finally:
        audit.close()
