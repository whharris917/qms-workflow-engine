"""Audit trail operations for plan execution."""

from __future__ import annotations

from datetime import datetime, timezone

from .types import ExecutionState, PlanDefinition, Snapshot, is_executable


def record_snapshot(
    plan: PlanDefinition,
    state: ExecutionState,
    row: int,
    actor: str,
    timestamp: str | None = None,
) -> Snapshot:
    """Record a timestamped snapshot of the entire row's execution state.

    Captures all column values (including blanks) at the current moment.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Capture all column values for this row
    values: dict[str, str] = {}
    for ci in range(plan.num_cols):
        values[str(ci)] = state.get_cell(row, ci)

    snapshot = Snapshot(values=values, timestamp=timestamp, actor=actor)

    key = str(row)
    if key not in state.history:
        state.history[key] = []
    # Newest first
    state.history[key].insert(0, snapshot)

    return snapshot


def get_history(state: ExecutionState, row: int) -> list[Snapshot]:
    """Get the audit trail for a row, newest first."""
    return state.history.get(str(row), [])
