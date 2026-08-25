from __future__ import annotations

from pathlib import Path

from interopera.canonical import canonical_bytes, sha256_bytes
from interopera.graph.schema import PropertyGraph


def canonical_graph_bytes(graph: PropertyGraph) -> bytes:
    normalized = graph.model_copy(update={
        "nodes": tuple(sorted(graph.nodes, key=lambda node: node.id)),
        "edges": tuple(sorted(graph.edges, key=lambda edge: edge.id)),
    })
    data = normalized.model_dump(mode="python")
    for node in data["nodes"]:
        if node["label"] == "SourceDocument":
            node["properties"].pop("registered_at", None)
        for provenance in node["provenance"]:
            provenance["ingestion_time"] = "1970-01-01T00:00:00+00:00"
    for edge in data["edges"]:
        for provenance in edge["provenance"]:
            provenance["ingestion_time"] = "1970-01-01T00:00:00+00:00"
    return canonical_bytes(data)


def graph_sha256(graph: PropertyGraph) -> str:
    return sha256_bytes(canonical_graph_bytes(graph))


def save_graph(path: Path, graph: PropertyGraph) -> str:
    data = canonical_graph_bytes(graph)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_bytes(data)


def load_graph(path: Path) -> PropertyGraph:
    return PropertyGraph.model_validate_json(path.read_bytes())
