"""Load, validate, and save DDR intermediate JSON (Pydantic `DDRIntermediate`)."""

from __future__ import annotations

import json
from pathlib import Path

from ddr_builder.schema import DDRIntermediate


def load_ddr_intermediate(path: str | Path) -> DDRIntermediate:
    """Load `ddr_intermediate.json` from disk."""
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return DDRIntermediate.model_validate(data)


def save_ddr_intermediate(ddr: DDRIntermediate, path: str | Path) -> None:
    Path(path).write_text(ddr.model_dump_json(indent=2), encoding="utf-8")
