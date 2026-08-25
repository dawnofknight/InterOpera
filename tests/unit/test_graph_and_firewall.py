from __future__ import annotations

from pathlib import Path

import pytest

from interopera.errors import NarrativeFirewallFailed
from interopera.graph.queries import duration_breach_route
from interopera.graph.repository import GraphRepository
from interopera.graph.serialization import canonical_graph_bytes, load_graph
from interopera.graph.validation import validate_graph
from interopera.narrative.firewall import apply_firewall

ROOT = Path(__file__).resolve().parents[2]


def test_approved_graph_validates_and_is_canonical() -> None:
    path = ROOT / "approved_graph/meridian_guidelines_v2_1.json"
    graph = load_graph(path)
    validate_graph(graph)
    assert canonical_graph_bytes(graph) == path.read_bytes()


def test_required_duration_route() -> None:
    result = duration_breach_route(GraphRepository(load_graph(ROOT / "approved_graph/meridian_guidelines_v2_1.json")))
    assert result["action"] == "action:pm_notification_within_1h"
    assert result["owners"] == ["owner:portfolio_manager"]
    assert result["source_chunks"]


def test_firewall_substitutes_only_ledger_numbers() -> None:
    final, evidence = apply_firewall("The duration is {{duration}} and remains within its approved range.",
                                     {"duration": "3.88 yrs"})
    assert final == "The duration is 3.88 yrs and remains within its approved range."
    assert evidence["result"] == "PASS"


@pytest.mark.parametrize("response", ("The value is 99.5%.", "There are ninety-nine concerns.",
                                      "Value {{unknown}}."))
def test_firewall_rejects_numeric_or_unknown_content(response: str) -> None:
    with pytest.raises(NarrativeFirewallFailed):
        apply_firewall(response, {"duration": "3.88 yrs"})

