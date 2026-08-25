from __future__ import annotations

from interopera.domain.models import ComputedFigure


def reconcile(figures: tuple[ComputedFigure, ...], expected: tuple[dict[str, str], ...],
              trace_hashes: dict[str, str]) -> dict[str, object]:
    by_metric = {figure.metric: figure for figure in figures}
    rows: list[dict[str, object]] = []
    for target in expected:
        figure = by_metric.get(target["metric"])
        if figure is None:
            rows.append({"metric": target["metric"], "result": "FAIL", "reason": "missing figure"})
            continue
        comparisons = {
            "value": figure.display_value == target["value"],
            "limit": figure.display_limit == target["limit"],
            "utilization": figure.display_utilization == target["utilization"],
            "status": figure.status.value == target["status"],
        }
        rows.append({"figure_id": figure.figure_id, "metric": figure.metric,
            "expected": {k: target[k] for k in ("value", "limit", "utilization", "status")},
            "actual": {"value": figure.display_value, "limit": figure.display_limit,
                       "utilization": figure.display_utilization, "status": figure.status.value},
            "display_fields": comparisons, "trace": "PASS" if figure.figure_id in trace_hashes else "FAIL",
            "result": "PASS" if all(comparisons.values()) and figure.figure_id in trace_hashes else "FAIL"})
    expected_metrics = {row["metric"] for row in expected}
    for figure in figures:
        if figure.metric not in expected_metrics:
            rows.append({"figure_id": figure.figure_id, "metric": figure.metric, "result": "FAIL", "reason": "unexpected figure"})
    passed = len(rows) == len(expected) and all(row["result"] == "PASS" for row in rows)
    return {"result": "PASS" if passed else "FAIL", "passed": sum(row["result"] == "PASS" for row in rows),
            "failed": sum(row["result"] != "PASS" for row in rows), "rows": rows}
