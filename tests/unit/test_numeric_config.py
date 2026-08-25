from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from interopera.computation.formatting import format_duration, format_ratio, format_utilization
from interopera.config.loader import load_config
from interopera.config.models import FirmConfig
from interopera.domain.rating_scale import at_or_above, at_or_below

ROOT = Path(__file__).resolve().parents[2]


def test_firm_a_rounding() -> None:
    config, _ = load_config(ROOT / "config/firm_a.yaml")
    assert format_ratio(Decimal("0.35"), config) == "35.0%"
    assert format_utilization(Decimal("0.583333333333"), config) == "58.3%"
    assert format_duration(Decimal("3.879"), config) == "3.88 yrs"


def test_firm_b_truncates_basis_points() -> None:
    config, _ = load_config(ROOT / "config/firm_b.yaml")
    assert format_utilization(Decimal("0.583333333333"), config) == "5833 bps"
    assert format_utilization(Decimal("0.4563529"), config) == "4563 bps"


def test_rating_scale_is_explicit() -> None:
    assert at_or_below("BB", "BB+")
    assert at_or_above("BBB-", "BBB-")
    assert not at_or_above("BB", "BBB-")
    assert not at_or_below(None, "BB+")


def test_unknown_config_strategy_fails() -> None:
    config, _ = load_config(ROOT / "config/firm_a.yaml")
    data = config.model_dump(mode="python")
    data["aggregate_non_ig"]["base_membership"]["strategy"] = "magic"
    with pytest.raises(ValidationError):
        FirmConfig.model_validate(data)


def test_computation_has_no_firm_name_branches() -> None:
    source = "\n".join(path.read_text() for path in (ROOT / "src/interopera/computation").glob("*.py"))
    assert "firm_a" not in source
    assert "firm_b" not in source

