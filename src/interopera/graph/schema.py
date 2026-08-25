from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from interopera.domain.models import Provenance


class GraphModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Node(GraphModel):
    id: str
    label: str
    properties: dict[str, Any]
    provenance: tuple[Provenance, ...]


class Edge(GraphModel):
    id: str
    label: str
    source: str
    target: str
    schema_version: str = "1.0"
    provenance: tuple[Provenance, ...]


class PropertyGraph(GraphModel):
    schema_version: str = "1.0"
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]

