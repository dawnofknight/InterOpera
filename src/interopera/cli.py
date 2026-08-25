from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from interopera.audit.store import AuditStore
from interopera.audit.verifier import verify_chain
from interopera.errors import InterOperaError, ReconciliationMismatch
from interopera.graph.queries import duration_breach_route
from interopera.graph.repository import GraphRepository
from interopera.graph.serialization import load_graph
from interopera.graph.validation import validate_graph
from interopera.orchestration.pipeline import approve_graph, run_pipeline
from interopera.reconciliation.answer_key import load_answer_key

# Runtime assets (config, sample_docs, approved_graph) belong to the checkout/image,
# not the installed package location. Docker and the documented local commands run
# from the repository root.
ROOT = Path.cwd().resolve()


def _path(value: str) -> Path:
    return Path(value).resolve()


def _common_run(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--firm", required=True)
    parser.add_argument("--guidelines", default="sample_docs/sample_fund_guidelines.pdf")
    parser.add_argument("--holdings", default="sample_docs/sample_holdings.csv")
    parser.add_argument("--template", default="sample_docs/report_template.xlsx")
    parser.add_argument("--answer-key")
    parser.add_argument("--output", default="output")
    parser.add_argument("--approved-dir", default="approved_graph")
    parser.add_argument("--strict-reconcile", action="store_true")
    parser.add_argument("--narrative-provider", default="none", choices=("none",))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="interopera")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    _common_run(run)
    commands.add_parser("demo")
    trace = commands.add_parser("trace")
    trace.add_argument("--run-id", required=True)
    trace.add_argument("--figure", required=True)
    trace.add_argument("--output", default="output")
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--run-id", required=True)
    reconcile.add_argument("--answer-key", required=True)
    reconcile.add_argument("--output", default="output")
    graph = commands.add_parser("graph")
    graph_commands = graph.add_subparsers(dest="graph_command", required=True)
    approve = graph_commands.add_parser("approve")
    approve.add_argument("--guidelines", default="sample_docs/sample_fund_guidelines.pdf")
    approve.add_argument("--holdings", default="sample_docs/sample_holdings.csv")
    approve.add_argument("--approved-dir", default="approved_graph")
    validate = graph_commands.add_parser("validate")
    validate.add_argument("--graph", default="approved_graph/meridian_guidelines_v2_1.json")
    query = graph_commands.add_parser("query")
    query.add_argument("--name", required=True, choices=("duration-breach-route",))
    query.add_argument("--graph", default="approved_graph/meridian_guidelines_v2_1.json")
    audit = commands.add_parser("audit")
    audit_commands = audit.add_subparsers(dest="audit_command", required=True)
    verify = audit_commands.add_parser("verify")
    verify.add_argument("--database", default="output/audit/audit.sqlite3")
    verify.add_argument("--run-id", required=True)
    return parser


def _run(args: argparse.Namespace) -> dict[str, Any]:
    return run_pipeline(firm=_path(args.firm), guidelines=_path(args.guidelines),
        holdings=_path(args.holdings), template=_path(args.template), output=_path(args.output),
        approved_dir=_path(args.approved_dir), answer_key=_path(args.answer_key) if args.answer_key else None,
        strict_reconcile=args.strict_reconcile)


def _demo() -> dict[str, Any]:
    common = dict(guidelines=ROOT / "sample_docs/sample_fund_guidelines.pdf",
        holdings=ROOT / "sample_docs/sample_holdings.csv", template=ROOT / "sample_docs/report_template.xlsx",
        output=ROOT / "output", approved_dir=ROOT / "approved_graph")
    firm_a = run_pipeline(firm=ROOT / "config/firm_a.yaml",
        answer_key=ROOT / "sample_docs/firm_A_answer_key.xlsx", strict_reconcile=True, **common)
    firm_b = run_pipeline(firm=ROOT / "config/firm_b.yaml", strict_reconcile=False, **common)
    figures = json.loads((Path(firm_b["run_dir"]) / "computed_figures.json").read_text())
    by_id = {figure["figure_id"]: figure for figure in figures}
    checks = {
        "aggregate_value": by_id["aggregate_non_ig_exposure"]["display_value"] == "21.0%",
        "aggregate_status": by_id["aggregate_non_ig_exposure"]["status"] == "BREACH",
        "gre_value": by_id["largest_gre_issuer"]["display_value"] == "13.0%",
        "gre_status": by_id["largest_gre_issuer"]["status"] == "BREACH",
        "bps": by_id["allocation_sgs"]["display_utilization"] == "5833 bps",
    }
    if not all(checks.values()):
        raise ReconciliationMismatch(f"Firm B expected-value validation failed: {checks}")
    return {"result": "PASS", "firm_a": firm_a, "firm_b": firm_b, "firm_b_checks": checks}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result: Any
        if args.command == "run":
            result = _run(args)
        elif args.command == "demo":
            result = _demo()
        elif args.command == "trace":
            path = _path(args.output) / args.run_id.removeprefix("sha256:") / "traces.json"
            traces = json.loads(path.read_text())
            result = next((trace for trace in traces if trace["figure_id"] == args.figure), None)
            if result is None:
                parser.error(f"Figure not found: {args.figure}")
        elif args.command == "reconcile":
            run_dir = _path(args.output) / args.run_id.removeprefix("sha256:")
            actual = {row["metric"]: row for row in json.loads((run_dir / "computed_figures.json").read_text())}
            rows = []
            for expected in load_answer_key(_path(args.answer_key)):
                figure = actual.get(expected["metric"])
                passed = figure is not None and all((figure["display_value"], figure["display_limit"],
                    figure["display_utilization"], figure["status"])[index] == expected[key]
                    for index, key in enumerate(("value", "limit", "utilization", "status")))
                rows.append({"metric": expected["metric"], "result": "PASS" if passed else "FAIL"})
            result = {"result": "PASS" if all(row["result"] == "PASS" for row in rows) else "FAIL", "rows": rows}
        elif args.command == "graph" and args.graph_command == "approve":
            result = approve_graph(_path(args.guidelines), _path(args.holdings), _path(args.approved_dir))
        elif args.command == "graph" and args.graph_command == "validate":
            graph = load_graph(_path(args.graph))
            validate_graph(graph)
            result = {"result": "PASS", "nodes": len(graph.nodes), "edges": len(graph.edges)}
        elif args.command == "graph" and args.graph_command == "query":
            result = duration_breach_route(GraphRepository(load_graph(_path(args.graph))))
        elif args.command == "audit" and args.audit_command == "verify":
            store = AuditStore(_path(args.database))
            try:
                result = {"result": "PASS", "chain_head": verify_chain(store, args.run_id)}
            finally:
                store.close()
        else:
            parser.error("Unsupported command")
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except InterOperaError as exc:
        print(json.dumps({"error": exc.code, "message": str(exc)}), file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
