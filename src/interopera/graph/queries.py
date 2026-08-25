from __future__ import annotations

from interopera.graph.repository import GraphRepository


def duration_breach_route(repository: GraphRepository) -> dict[str, object]:
    action, owners = repository.breach_route("limit:portfolio_modified_duration")
    source_edges = repository.outgoing(action.id, "DERIVED_FROM")
    return {"metric": "metric:portfolio_duration", "limit": "limit:portfolio_modified_duration",
            "action": action.id, "owners": [owner.id for owner in owners],
            "source_chunks": [edge.target for edge in source_edges]}

