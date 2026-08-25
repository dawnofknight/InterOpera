from __future__ import annotations

from enum import StrEnum


class Status(StrEnum):
    OK = "OK"
    AT_LIMIT = "AT LIMIT"
    BREACH = "BREACH"
    ERROR = "ERROR"


class LimitKind(StrEnum):
    MIN = "min"
    MAX = "max"
    RANGE = "range"


class NumericUnit(StrEnum):
    RATIO = "ratio"
    YEARS = "years"
    SGD_PER_BP = "sgd_per_bp"
    BPS = "bps"

