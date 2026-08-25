from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from interopera.canonical import canonical_sha256
from interopera.config.models import FirmConfig
from interopera.errors import ConfigSchemaError


def load_config(path: Path) -> tuple[FirmConfig, str]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        config = FirmConfig.model_validate(raw)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        raise ConfigSchemaError(f"Invalid firm configuration at {path}: {exc}") from exc
    return config, canonical_sha256(config)

