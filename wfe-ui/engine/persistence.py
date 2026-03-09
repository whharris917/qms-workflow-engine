"""Persistence for plan definitions."""

from __future__ import annotations

import json
from pathlib import Path

from .types import ColumnDef, PlanDefinition


def load_plan(data_dir: Path, cr_id: str) -> PlanDefinition | None:
    """Load a plan definition from a CR JSON file."""
    path = data_dir / f"{cr_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))

    columns = []
    for c in data.get("plan_columns", []):
        if isinstance(c, str):
            columns.append(ColumnDef(name=c, type=""))
        else:
            columns.append(ColumnDef.from_dict(c))

    return PlanDefinition(
        cr_id=data["id"],
        columns=columns,
        rows=data.get("plan_rows", []),
        table_properties=data.get("table_properties", {}),
    )
