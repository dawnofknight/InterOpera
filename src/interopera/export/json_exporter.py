from __future__ import annotations

from pathlib import Path
from typing import Any

from interopera.canonical import write_canonical


def export_json(path: Path, value: Any) -> str:
    return write_canonical(path, value)

