from __future__ import annotations

from collections import Counter

from interopera.errors import GraphSchemaError
from interopera.graph.schema import PropertyGraph


def validate_graph(graph: PropertyGraph) -> None:
    node_ids = [node.id for node in graph.nodes]
    edge_ids = [edge.id for edge in graph.edges]
    duplicates = [key for key, count in Counter(node_ids + edge_ids).items() if count > 1]
    if duplicates:
        raise GraphSchemaError(f"Duplicate graph IDs: {duplicates}")
    known = set(node_ids)
    chunks = {node.id for node in graph.nodes if node.label == "SourceChunk"}
    for node in graph.nodes:
        if not node.provenance:
            raise GraphSchemaError("Node has no provenance", entity_id=node.id)
        for provenance in node.provenance:
            if provenance.chunk_id not in chunks:
                raise GraphSchemaError("Node has unresolved provenance chunk", entity_id=node.id)
    for edge in graph.edges:
        if edge.source not in known or edge.target not in known:
            raise GraphSchemaError("Dangling edge", entity_id=edge.id)
        if not edge.provenance:
            raise GraphSchemaError("Edge has no provenance", entity_id=edge.id)
        for provenance in edge.provenance:
            if provenance.chunk_id not in chunks:
                raise GraphSchemaError("Edge has unresolved provenance chunk", entity_id=edge.id)
    for position in (node for node in graph.nodes if node.label == "Position"):
        outgoing = [edge.label for edge in graph.edges if edge.source == position.id]
        if outgoing.count("BELONGS_TO") != 1 or outgoing.count("ISSUED_BY") != 1:
            raise GraphSchemaError("Position classification invariant failed", entity_id=position.id)

