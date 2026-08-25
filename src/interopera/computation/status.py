from __future__ import annotations

from decimal import Decimal

from interopera.domain.enums import Status
from interopera.domain.models import LimitRule


def evaluate_status(actual: Decimal, rule: LimitRule) -> Status:
    if rule.min_value is not None and actual < rule.min_value:
        return Status.BREACH
    if rule.max_value is not None and actual > rule.max_value:
        return Status.BREACH
    if rule.max_value is not None and actual == rule.max_value:
        return Status.AT_LIMIT
    return Status.OK


def is_material_breach(actual: Decimal, rule: LimitRule) -> bool:
    return rule.max_value is not None and actual > rule.max_value * Decimal("1.10")

