from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class QualitativeNarrativeRequest:
    metric_key: str
    qualitative_status: str
    allowed_placeholders: tuple[str, ...]


class NarrativePort(Protocol):
    def draft(self, request: QualitativeNarrativeRequest) -> str: ...


class NoneNarrativeAdapter:
    def draft(self, request: QualitativeNarrativeRequest) -> str:
        return ""


class FakeNarrativeAdapter:
    def __init__(self, response: str) -> None:
        self.response = response

    def draft(self, request: QualitativeNarrativeRequest) -> str:
        return self.response

