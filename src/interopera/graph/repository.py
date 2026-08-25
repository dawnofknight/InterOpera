from __future__ import annotations

from decimal import Decimal

from interopera.domain.models import Citation, HoldingRecord, LimitRule, TraceStep
from interopera.errors import GraphSchemaError
from interopera.graph.schema import Edge, Node, PropertyGraph


class GraphRepository:
    """Typed graph read port used by the computation engine."""

    def __init__(self, graph: PropertyGraph) -> None:
        self.graph = graph
        self.nodes = {node.id: node for node in graph.nodes}
        self.edges = {edge.id: edge for edge in graph.edges}

    def node(self, identifier: str) -> Node:
        try:
            return self.nodes[identifier]
        except KeyError as exc:
            raise GraphSchemaError("Graph node not found", entity_id=identifier) from exc

    def outgoing(self, source: str, label: str | None = None) -> tuple[Edge, ...]:
        return tuple(sorted((edge for edge in self.graph.edges if edge.source == source and (label is None or edge.label == label)), key=lambda edge: edge.id))

    def incoming(self, target: str, label: str | None = None) -> tuple[Edge, ...]:
        return tuple(sorted((edge for edge in self.graph.edges if edge.target == target and (label is None or edge.label == label)), key=lambda edge: edge.id))

    def portfolio_positions(self, portfolio_id: str = "portfolio:meridian_fixed_income") -> tuple[HoldingRecord, ...]:
        records = []
        for edge in self.outgoing(portfolio_id, "HOLDS"):
            node = self.node(edge.target)
            records.append(HoldingRecord(**node.properties, provenance=node.provenance[0]))
        return tuple(sorted(records, key=lambda record: record.instrument_id))

    def positions_for_asset_class(self, class_key: str) -> tuple[HoldingRecord, ...]:
        target = f"asset_class:{class_key}"
        identifiers = {edge.source for edge in self.incoming(target, "BELONGS_TO")}
        return tuple(record for record in self.portfolio_positions() if f"position:{record.instrument_id}" in identifiers)

    def aggregate_asset_classes(self, aggregate_id: str) -> tuple[str, ...]:
        return tuple(sorted(edge.source.removeprefix("asset_class:") for edge in self.incoming(aggregate_id, "CONTRIBUTES_TO")))

    def liquid_asset_classes(self, bucket_id: str) -> tuple[str, ...]:
        return tuple(sorted(edge.source.removeprefix("asset_class:") for edge in self.incoming(bucket_id, "INCLUDED_IN")))

    def limit_for(self, figure_id: str) -> LimitRule:
        identifier = f"limit:{figure_id}"
        node = self.node(identifier)
        props = node.properties
        return LimitRule(
            id=identifier, metric_id=str(props["metric_id"]), kind=str(props["kind"]),
            min_value=Decimal(str(props["min_value"])) if props.get("min_value") is not None else None,
            max_value=Decimal(str(props["max_value"])) if props.get("max_value") is not None else None,
            unit=str(props["unit"]), provenance=node.provenance,
        )

    def edge_step(self, edge: Edge, ordinal: int) -> TraceStep:
        return TraceStep(ordinal=ordinal, from_node_id=edge.source, edge_id=edge.id,
                         relation=edge.label, to_node_id=edge.target,
                         provenance_refs=tuple(sorted({p.chunk_id for p in edge.provenance})))

    def trace_for(self, figure_id: str, positions: tuple[HoldingRecord, ...], config_rule_ids: tuple[str, ...]) -> tuple[TraceStep, ...]:
        selected: list[Edge] = []
        for record in sorted(positions, key=lambda item: item.instrument_id):
            selected.extend(self.outgoing(f"position:{record.instrument_id}", "DERIVED_FROM"))
        limit = self.node(f"limit:{figure_id}")
        selected.extend(self.outgoing(limit.id, "DERIVED_FROM"))
        for rule_id in config_rule_ids:
            selected.extend(self.outgoing(rule_id, "DERIVED_FROM"))
        return tuple(self.edge_step(edge, index) for index, edge in enumerate(selected, start=1))

    def citations_for(self, trace: tuple[TraceStep, ...]) -> tuple[Citation, ...]:
        found: dict[str, Citation] = {}
        for step in trace:
            for reference in step.provenance_refs:
                chunk = self.node(reference)
                provenance = chunk.provenance[0]
                found[reference] = Citation(source_doc=provenance.source_doc, page=provenance.page,
                    row_number=provenance.row_number, chunk_id=reference,
                    passage_summary=provenance.passage_summary)
        return tuple(sorted(found.values(), key=lambda c: (c.source_doc, c.page or 0, c.row_number or 0, c.chunk_id)))

    def breach_route(self, limit_id: str) -> tuple[Node, tuple[Node, ...]]:
        actions = self.outgoing(limit_id, "HAS_BREACH_ACTION")
        if len(actions) != 1:
            raise GraphSchemaError("Expected one breach action", entity_id=limit_id)
        action = self.node(actions[0].target)
        owners = tuple(self.node(edge.target) for edge in self.outgoing(action.id, "NOTIFIES"))
        return action, owners
