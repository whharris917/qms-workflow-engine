"""Persistence for plan definitions and execution state."""

from __future__ import annotations

import json
from pathlib import Path

from .types import ColumnDef, PlanDefinition, ExecutionState


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


def load_execution_state(data_dir: Path, cr_id: str) -> ExecutionState:
    """Load execution state, or return a fresh state if none exists."""
    path = data_dir / f"{cr_id}.execution.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return ExecutionState.from_dict(data)
    return ExecutionState(cr_id=cr_id)


def save_execution_state(data_dir: Path, state: ExecutionState):
    """Persist execution state to disk."""
    path = data_dir / f"{state.cr_id}.execution.json"
    path.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
