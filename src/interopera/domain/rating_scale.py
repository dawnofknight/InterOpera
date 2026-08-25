from __future__ import annotations

from interopera.errors import HoldingValidationError

RATINGS = (
    "AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-",
    "BB+", "BB", "BB-", "B+", "B", "B-", "CCC+", "CCC", "CCC-", "CC", "C", "D",
)
_RANK = {rating: index for index, rating in enumerate(RATINGS)}


def validate_rating(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    if value not in _RANK:
        raise HoldingValidationError(f"Unknown credit rating: {value}")
    return value


def at_or_below(value: str | None, threshold: str) -> bool:
    return value is not None and _RANK[value] >= _RANK[threshold]


def at_or_above(value: str | None, threshold: str) -> bool:
    return value is not None and _RANK[value] <= _RANK[threshold]

