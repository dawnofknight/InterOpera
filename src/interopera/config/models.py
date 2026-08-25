from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ConfigModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NavConfig(ConfigModel):
    source: Literal["sum_position_market_value"]
    currency: Literal["SGD"]


class MembershipConfig(ConfigModel):
    strategy: Literal["asset_class_membership"]
    asset_classes: tuple[str, ...]


class RatingTransitionConfig(ConfigModel):
    strategy: Literal["rating_with_transition"]
    current_rating_at_or_below: str
    prior_rating_at_or_above: str
    require_downgraded_from: bool


class AggregateConfig(ConfigModel):
    base_membership: MembershipConfig
    additions: tuple[RatingTransitionConfig, ...]
    deduplicate_by: Literal["instrument_id"]


class ConcentrationRule(ConfigModel):
    issuer_types: tuple[Literal["government", "corporate", "GRE", "spv", "cash"], ...]
    exclude_issuers: tuple[str, ...] = ()
    grouping_key: Literal["issuer_name", "parent_issuer"]
    missing_group_key: Literal["error", "fallback_to_issuer"] = "error"


class ConcentrationConfig(ConfigModel):
    corporate: ConcentrationRule
    gre: ConcentrationRule


class LiquidityConfig(ConfigModel):
    condition: Literal["normal", "stressed"]
    bucket_id: str


class FormulaConfig(ConfigModel):
    formula: Literal["actual_divided_by_limit", "not_applicable", "floor_coverage"]


class UtilizationConfig(ConfigModel):
    max_or_upper_bound: FormulaConfig
    min_or_lower_bound: FormulaConfig
    representation: Literal["percent", "basis_points"]
    decimals: int
    rounding: Literal["ROUND_HALF_UP", "ROUND_DOWN"]


class RatioFormat(ConfigModel):
    percent_decimals: int
    rounding: Literal["ROUND_HALF_UP", "ROUND_DOWN"]


class DurationFormat(ConfigModel):
    decimals: int
    rounding: Literal["ROUND_HALF_UP", "ROUND_DOWN"]


class CurrencyFormat(ConfigModel):
    decimals: int
    thousands_separator: bool


class ValueFormatting(ConfigModel):
    ratios: RatioFormat
    duration: DurationFormat
    currency: CurrencyFormat


class MetricOverride(ConfigModel):
    utilization_formula: Literal["floor_coverage"]


class FirmConfig(ConfigModel):
    schema_version: Literal["1.0"]
    firm_id: str
    display_name: str
    nav: NavConfig
    aggregate_non_ig: AggregateConfig
    concentration: ConcentrationConfig
    liquidity: LiquidityConfig
    utilization: UtilizationConfig
    value_formatting: ValueFormatting
    metric_overrides: dict[str, MetricOverride] = {}

