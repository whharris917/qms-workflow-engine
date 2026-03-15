"""Data types for the execution engine."""

from __future__ import annotations

from dataclasses import dataclass, field


# --- Column type constants ---

EXECUTABLE_TYPES = frozenset({
    "ex-free-text", "ex-choice-list", "ex-cross-reference", "ex-signature",
    # legacy compat
    "free-text", "choice-list", "cross-reference", "signature",
})

AUTO_EXECUTED_TYPES = frozenset({"ae-acceptance-criteria"})

CHOICE_LIST_TYPES = frozenset({"ex-choice-list", "choice-list"})
CROSS_REF_TYPES = frozenset({"ex-cross-reference", "cross-reference"})
SIGNATURE_TYPES = frozenset({"ex-signature", "signature"})
FREE_TEXT_EXEC_TYPES = frozenset({"ex-free-text", "free-text"})


def is_executable(col_type: str) -> bool:
    return col_type in EXECUTABLE_TYPES


def is_auto_executed(col_type: str) -> bool:
    return col_type in AUTO_EXECUTED_TYPES


def is_choice_list(col_type: str) -> bool:
    return col_type in CHOICE_LIST_TYPES


def is_cross_ref(col_type: str) -> bool:
    return col_type in CROSS_REF_TYPES


def is_signature(col_type: str) -> bool:
    return col_type in SIGNATURE_TYPES


def is_prerequisite(col_type: str) -> bool:
    return col_type == "ne-prerequisite"


# --- Plan definition (authoring artifact) ---

@dataclass
class ColumnDef:
    name: str
    type: str
    choices: list[str] | None = None
    rule: dict | None = None
    cascade_revert: bool | None = None  # None = use type default

    @property
    def should_cascade_revert(self) -> bool:
        """Whether this column should be reverted during cascade.

        Explicit per-column setting wins; otherwise use type default.
        Cross-reference columns default to exempt (False).
        """
        if self.cascade_revert is not None:
            return self.cascade_revert
        # Type defaults: cross-references are exempt
        if is_cross_ref(self.type):
            return False
        return True

    @classmethod
    def from_dict(cls, d: dict) -> ColumnDef:
        return cls(
            name=d.get("name", ""),
            type=d.get("type", ""),
            choices=d.get("choices"),
            rule=d.get("rule"),
            cascade_revert=d.get("cascade_revert"),
        )

    def to_dict(self) -> dict:
        d = {"name": self.name, "type": self.type}
        if self.choices is not None:
            d["choices"] = self.choices
        if self.rule is not None:
            d["rule"] = self.rule
        if self.cascade_revert is not None:
            d["cascade_revert"] = self.cascade_revert
        return d


@dataclass
class PlanDefinition:
    cr_id: str
    columns: list[ColumnDef]
    rows: list[list[str]]
    table_properties: dict = field(default_factory=dict)

    @property
    def sequential_execution(self) -> bool:
        return self.table_properties.get("sequentialExecution", False)

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        return len(self.columns)

    def executable_column_order(self) -> list[int]:
        """Column indices that are executable, in left-to-right order."""
        return [ci for ci, col in enumerate(self.columns) if is_executable(col.type)]


# --- Execution state (runtime artifact) ---

@dataclass
class CellValue:
    value: str
    updated_at: str
    updated_by: str

    def to_dict(self) -> dict:
        return {"value": self.value, "updated_at": self.updated_at, "updated_by": self.updated_by}

    @classmethod
    def from_dict(cls, d: dict) -> CellValue:
        return cls(value=d["value"], updated_at=d["updated_at"], updated_by=d["updated_by"])


@dataclass
class Snapshot:
    values: dict[str, str]  # col_index (as string) -> value
    timestamp: str
    actor: str

    def to_dict(self) -> dict:
        return {"values": self.values, "timestamp": self.timestamp, "actor": self.actor}

    @classmethod
    def from_dict(cls, d: dict) -> Snapshot:
        return cls(values=d["values"], timestamp=d["timestamp"], actor=d["actor"])


@dataclass
class ExecutionState:
    cr_id: str
    status: str = "not-started"  # not-started | in-progress | completed
    started_at: str | None = None
    cells: dict[str, CellValue] = field(default_factory=dict)  # "row:col" -> CellValue
    history: dict[str, list[Snapshot]] = field(default_factory=dict)  # "row" -> [snapshots]
    issue_counters: dict[str, int] = field(default_factory=dict)  # "VAR" -> 1, "ER" -> 0

    def get_cell(self, row: int, col: int) -> str:
        """Get the current value of a cell, or empty string if not set."""
        key = f"{row}:{col}"
        cv = self.cells.get(key)
        return cv.value if cv else ""

    def set_cell(self, row: int, col: int, value: str, timestamp: str, actor: str):
        key = f"{row}:{col}"
        self.cells[key] = CellValue(value=value, updated_at=timestamp, updated_by=actor)

    def clear_cell(self, row: int, col: int):
        key = f"{row}:{col}"
        self.cells.pop(key, None)

    def next_issue_id(self, issue_type: str) -> str:
        """Get the next sequential issue ID for a given type."""
        count = self.issue_counters.get(issue_type, 0) + 1
        self.issue_counters[issue_type] = count
        return f"{self.cr_id}-{issue_type}-{count:03d}"

    def to_dict(self) -> dict:
        d = {
            "cr_id": self.cr_id,
            "status": self.status,
            "started_at": self.started_at,
            "cells": {k: v.to_dict() for k, v in self.cells.items()},
            "history": {k: [s.to_dict() for s in v] for k, v in self.history.items()},
        }
        if self.issue_counters:
            d["issue_counters"] = self.issue_counters
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ExecutionState:
        return cls(
            cr_id=d["cr_id"],
            status=d.get("status", "not-started"),
            started_at=d.get("started_at"),
            cells={k: CellValue.from_dict(v) for k, v in d.get("cells", {}).items()},
            history={k: [Snapshot.from_dict(s) for s in v] for k, v in d.get("history", {}).items()},
            issue_counters=d.get("issue_counters", {}),
        )


# --- Response types (agent-facing) ---

@dataclass
class CellState:
    row: int
    col: int
    column_name: str
    column_type: str
    value: str
    display_value: str
    status: str  # empty | filled | signed | na | issued | locked | gated | pass | pending | static
    locked_reason: str | None = None
    available_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = {
            "row": self.row,
            "col": self.col,
            "column_name": self.column_name,
            "column_type": self.column_type,
            "value": self.value,
            "display_value": self.display_value,
            "status": self.status,
            "available_actions": self.available_actions,
        }
        if self.locked_reason:
            d["locked_reason"] = self.locked_reason
        return d


@dataclass
class AcceptanceResult:
    passed: bool
    reason: str  # human-readable trace of the evaluation

    def to_dict(self) -> dict:
        return {"passed": self.passed, "reason": self.reason}


@dataclass
class RowState:
    row: int
    row_id: str  # e.g. "WF-Row-1"
    gated: bool
    gated_by: list[str]  # row IDs that block this row
    cells: list[CellState] = field(default_factory=list)
    acceptance: AcceptanceResult | None = None

    def to_dict(self) -> dict:
        d = {
            "row": self.row,
            "row_id": self.row_id,
            "gated": self.gated,
            "gated_by": self.gated_by,
            "cells": [c.to_dict() for c in self.cells],
        }
        if self.acceptance is not None:
            d["acceptance"] = self.acceptance.to_dict()
        return d


@dataclass
class PlanState:
    cr_id: str
    status: str
    columns: list[dict]
    rows: list[RowState]
    next_actions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "cr_id": self.cr_id,
            "status": self.status,
            "columns": self.columns,
            "rows": [r.to_dict() for r in self.rows],
            "next_actions": self.next_actions,
        }


@dataclass
class FillResult:
    ok: bool
    error: str | None = None
    row_state: RowState | None = None
    reverted_cells: list[dict] | None = None  # cells cleared by cascade revert
    snapshot: Snapshot | None = None

    def to_dict(self) -> dict:
        d: dict = {"ok": self.ok}
        if self.error:
            d["error"] = self.error
        if self.row_state:
            d["row_state"] = self.row_state.to_dict()
        if self.reverted_cells:
            d["reverted_cells"] = self.reverted_cells
        if self.snapshot:
            d["snapshot"] = self.snapshot.to_dict()
        return d
