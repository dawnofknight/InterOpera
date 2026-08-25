from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, getcontext

from interopera.computation.formatting import (
    format_currency, format_duration, format_limit, format_ratio, format_utilization,
)
from interopera.computation.status import evaluate_status, is_material_breach
from interopera.config.models import ConcentrationRule, FirmConfig
from interopera.domain.enums import NumericUnit
from interopera.domain.models import Citation, ComputedFigure, HoldingRecord, NumericValue
from interopera.domain.rating_scale import at_or_above, at_or_below
from interopera.errors import ConfiguredGroupKeyMissing, ZeroNav
from interopera.graph.repository import GraphRepository

getcontext().prec = 34

REPORT_ROWS = (
    ("allocation_sgs", "Allocation", "Singapore Government Securities", "sgs"),
    ("allocation_mas_bills", "Allocation", "MAS Bills", "mas_bills"),
    ("allocation_ig_corporate", "Allocation", "Investment Grade Corporate Bonds", "ig_corporate"),
    ("allocation_high_yield", "Allocation", "High Yield Bonds", "high_yield"),
    ("allocation_foreign_bonds", "Allocation", "Foreign Currency Bonds (hedged)", "foreign_bonds"),
    ("allocation_structured_credit", "Allocation", "Structured Credit (ABS/MBS)", "structured_credit"),
    ("allocation_cash", "Allocation", "Cash & Cash Equivalents", "cash"),
)


class ComputationEngine:
    def __init__(self, graph: GraphRepository, config: FirmConfig) -> None:
        self.graph = graph
        self.config = config
        self.positions = graph.portfolio_positions()
        self.nav = sum((record.market_value_sgd for record in self.positions), Decimal(0))
        if self.nav <= 0:
            raise ZeroNav("Portfolio NAV is zero or negative")

    def _source_summary(self, figure_id: str, citations: tuple[Citation, ...]) -> str:
        policy = next((c for c in citations if c.source_doc.endswith(".pdf")), None)
        rows = sorted({c.row_number for c in citations if c.row_number is not None})
        row_text = f" rows {rows[0]}-{rows[-1]}" if rows else ""
        page_text = f" p.{policy.page}" if policy else ""
        return f"figure:{figure_id} -> limit:{figure_id} | sample_fund_guidelines.pdf{page_text}; sample_holdings.csv{row_text}"

    def _figure(self, figure_id: str, section: str, metric: str, actual: Decimal,
                unit: NumericUnit, calculation_id: str, config_keys: tuple[str, ...],
                utilization: Decimal | None, display_value: str) -> ComputedFigure:
        rule = self.graph.limit_for(figure_id)
        config_ids = tuple(f"method:{self.config.firm_id}:{key}" for key in config_keys)
        trace = self.graph.trace_for(figure_id, self.positions, config_ids)
        citations = self.graph.citations_for(trace)
        return ComputedFigure(
            figure_id=figure_id, section=section, metric=metric,
            raw_value=NumericValue(amount=actual, unit=unit), display_value=display_value,
            raw_limit=rule, display_limit=format_limit(rule), raw_utilization=utilization,
            display_utilization=format_utilization(utilization, self.config),
            status=evaluate_status(actual, rule), material_breach=is_material_breach(actual, rule),
            calculation_id=calculation_id, config_rule_ids=config_ids,
            input_node_ids=tuple(f"position:{p.instrument_id}" for p in self.positions),
            graph_path=trace, citations=citations,
            source_summary=self._source_summary(figure_id, citations), error=None,
        )

    def allocations(self) -> list[ComputedFigure]:
        output = []
        for figure_id, section, label, key in REPORT_ROWS:
            actual = sum((p.market_value_sgd for p in self.graph.positions_for_asset_class(key)), Decimal(0)) / self.nav
            rule = self.graph.limit_for(figure_id)
            utilization = actual / rule.max_value if rule.max_value is not None else None
            output.append(self._figure(figure_id, section, label, actual, NumericUnit.RATIO,
                "allocation.nav_ratio.v1", ("utilization", "formatting"), utilization,
                format_ratio(actual, self.config)))
        return output

    def aggregate_non_ig(self) -> ComputedFigure:
        selected: dict[str, HoldingRecord] = {}
        for key in self.graph.aggregate_asset_classes("aggregate:non_ig"):
            selected.update({p.instrument_id: p for p in self.graph.positions_for_asset_class(key)})
        for predicate in self.config.aggregate_non_ig.additions:
            for record in self.positions:
                qualifies = at_or_below(record.credit_rating, predicate.current_rating_at_or_below)
                prior = at_or_above(record.downgraded_from, predicate.prior_rating_at_or_above)
                if qualifies and prior and (not predicate.require_downgraded_from or record.downgraded_from is not None):
                    selected[record.instrument_id] = record
        actual = sum((p.market_value_sgd for p in selected.values()), Decimal(0)) / self.nav
        rule = self.graph.limit_for("aggregate_non_ig_exposure")
        assert rule.max_value is not None
        return self._figure("aggregate_non_ig_exposure", "Aggregate", "Aggregate non-IG exposure",
            actual, NumericUnit.RATIO, "aggregate.membership_union.nav_ratio.v1",
            ("aggregate_non_ig", "utilization", "formatting"), actual / rule.max_value,
            format_ratio(actual, self.config))

    def _concentration(self, figure_id: str, metric: str, settings: ConcentrationRule, key: str) -> ComputedFigure:
        groups: dict[str, Decimal] = defaultdict(Decimal)
        for record in self.positions:
            if record.issuer_type not in settings.issuer_types or record.issuer_name in settings.exclude_issuers:
                continue
            group = record.issuer_name if settings.grouping_key == "issuer_name" else record.parent_issuer
            if group is None:
                if settings.missing_group_key == "error":
                    raise ConfiguredGroupKeyMissing("Configured concentration grouping key is absent", entity_id=record.instrument_id)
                group = record.issuer_name
            groups[group] += record.market_value_sgd
        if not groups:
            actual = Decimal(0)
        else:
            winner = sorted(groups.items(), key=lambda item: (-item[1], item[0].casefold()))[0]
            actual = winner[1] / self.nav
        rule = self.graph.limit_for(figure_id)
        assert rule.max_value is not None
        return self._figure(figure_id, "Concentration", metric, actual, NumericUnit.RATIO,
            "concentration.group_max.nav_ratio.v1", (key, "utilization", "formatting"),
            actual / rule.max_value, format_ratio(actual, self.config))

    def liquidity(self) -> ComputedFigure:
        selected: dict[str, HoldingRecord] = {}
        for key in self.graph.liquid_asset_classes(self.config.liquidity.bucket_id):
            selected.update({p.instrument_id: p for p in self.graph.positions_for_asset_class(key)})
        actual = sum((p.market_value_sgd for p in selected.values()), Decimal(0)) / self.nav
        rule = self.graph.limit_for("liquid_assets_ratio")
        assert rule.min_value is not None
        utilization = actual / rule.min_value
        return self._figure("liquid_assets_ratio", "Liquidity", "Liquid assets ratio", actual,
            NumericUnit.RATIO, "liquidity.bucket.nav_ratio.v1",
            ("liquidity", "utilization", "formatting"), utilization, format_ratio(actual, self.config))

    def duration(self) -> ComputedFigure:
        actual = sum((p.market_value_sgd * p.modified_duration for p in self.positions), Decimal(0)) / self.nav
        return self._figure("portfolio_modified_duration", "Market risk", "Portfolio modified duration",
            actual, NumericUnit.YEARS, "market_risk.weighted_modified_duration.v1",
            ("formatting",), None, format_duration(actual, self.config))

    def dv01(self) -> ComputedFigure:
        actual = sum((p.market_value_sgd * p.modified_duration * Decimal("0.0001") for p in self.positions), Decimal(0))
        rule = self.graph.limit_for("portfolio_dv01")
        assert rule.max_value is not None
        return self._figure("portfolio_dv01", "Market risk", "Portfolio DV01", actual,
            NumericUnit.SGD_PER_BP, "market_risk.dv01_approximation.v1",
            ("utilization", "formatting"), actual / rule.max_value, format_currency(actual, self.config))

    def compute(self) -> tuple[ComputedFigure, ...]:
        figures = self.allocations()
        figures.extend((
            self.aggregate_non_ig(),
            self._concentration("largest_single_corporate_issuer", "Largest single corporate issuer", self.config.concentration.corporate, "corporate_grouping"),
            self._concentration("largest_gre_issuer", "Largest GRE issuer", self.config.concentration.gre, "gre_grouping"),
            self.liquidity(), self.duration(), self.dv01(),
        ))
        return tuple(figures)
