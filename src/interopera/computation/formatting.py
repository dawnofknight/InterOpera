from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from interopera.config.models import FirmConfig
from interopera.domain.models import LimitRule

ROUNDINGS = {"ROUND_HALF_UP": ROUND_HALF_UP, "ROUND_DOWN": ROUND_DOWN}


def quantum(decimals: int) -> Decimal:
    return Decimal(1).scaleb(-decimals)


def format_ratio(value: Decimal, config: FirmConfig) -> str:
    settings = config.value_formatting.ratios
    shown = (value * 100).quantize(quantum(settings.percent_decimals), rounding=ROUNDINGS[settings.rounding])
    return f"{shown:.{settings.percent_decimals}f}%"


def format_duration(value: Decimal, config: FirmConfig) -> str:
    settings = config.value_formatting.duration
    shown = value.quantize(quantum(settings.decimals), rounding=ROUNDINGS[settings.rounding])
    return f"{shown:.{settings.decimals}f} yrs"


def format_currency(value: Decimal, config: FirmConfig) -> str:
    settings = config.value_formatting.currency
    shown = value.quantize(quantum(settings.decimals), rounding=ROUND_HALF_UP)
    formatted = f"{shown:,.{settings.decimals}f}" if settings.thousands_separator else f"{shown:.{settings.decimals}f}"
    return f"SGD {formatted} / bp"


def format_utilization(value: Decimal | None, config: FirmConfig) -> str:
    if value is None:
        return "n/a"
    settings = config.utilization
    if settings.representation == "percent":
        shown = (value * 100).quantize(quantum(settings.decimals), rounding=ROUNDINGS[settings.rounding])
        return f"{shown:.{settings.decimals}f}%"
    shown = (value * 10000).quantize(Decimal("1"), rounding=ROUNDINGS[settings.rounding])
    return f"{shown:.0f} bps"


def _percent_limit(value: Decimal) -> str:
    shown = value * 100
    return f"{shown:.0f}%"


def format_limit(rule: LimitRule) -> str:
    if rule.unit == "nav_ratio":
        if rule.min_value is not None and rule.max_value is not None:
            return f"{_percent_limit(rule.min_value).removesuffix('%')}–{_percent_limit(rule.max_value)}"
        if rule.min_value is not None:
            return f"min {_percent_limit(rule.min_value)}"
        assert rule.max_value is not None
        return f"max {_percent_limit(rule.max_value)}"
    if rule.unit == "years":
        assert rule.min_value is not None and rule.max_value is not None
        return f"{rule.min_value:.1f}–{rule.max_value:.1f} yrs"
    assert rule.max_value is not None
    return f"max {rule.max_value:,.0f}"

