from __future__ import annotations

from interopera.canonical import canonical_sha256
from interopera.domain.models import ComputedFigure
from interopera.errors import TraceabilityError
from interopera.graph.repository import GraphRepository


def verify_figure(figure: ComputedFigure, repository: GraphRepository) -> str:
    if not figure.graph_path:
        raise TraceabilityError("Figure has no recorded graph path", entity_id=figure.figure_id)
    documents: set[str] = set()
    for step in figure.graph_path:
        edge = repository.edges.get(step.edge_id)
        if edge is None or edge.source != step.from_node_id or edge.target != step.to_node_id or edge.label != step.relation:
            raise TraceabilityError("Recorded graph step does not resolve", entity_id=figure.figure_id)
        if not edge.provenance:
            raise TraceabilityError("Recorded graph edge has no provenance", entity_id=edge.id)
        for reference in step.provenance_refs:
            chunk = repository.nodes.get(reference)
            if chunk is None or chunk.label != "SourceChunk":
                raise TraceabilityError("Trace chunk does not resolve", entity_id=reference)
            provenance = chunk.provenance[0]
            if chunk.properties.get("normalized_text_sha256") != provenance.chunk_sha256:
                raise TraceabilityError("Trace chunk hash mismatch", entity_id=reference)
            documents.add(provenance.source_doc)
    if not any(name.endswith(".csv") for name in documents):
        raise TraceabilityError("Figure trace has no holdings citation", entity_id=figure.figure_id)
    if not any(name.endswith(".pdf") for name in documents):
        raise TraceabilityError("Figure trace has no policy citation", entity_id=figure.figure_id)
    if figure.config_rule_ids and not any(name.endswith((".yaml", ".yml")) for name in documents):
        raise TraceabilityError("Figure trace has no configuration citation", entity_id=figure.figure_id)
    return canonical_sha256(figure.graph_path)


def verify_all(figures: tuple[ComputedFigure, ...], repository: GraphRepository) -> dict[str, str]:
    return {figure.figure_id: verify_figure(figure, repository) for figure in figures}

