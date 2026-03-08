"""Core execution engine for plan tables.

Implements all business logic: cell fill/sign, sequential locking,
prerequisite gating, cascading revert, and state computation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .types import (
    PlanDefinition,
    ExecutionState,
    CellState,
    RowState,
    PlanState,
    FillResult,
    AcceptanceResult,
    is_executable,
    is_auto_executed,
    is_choice_list,
    is_cross_ref,
    is_signature,
    is_prerequisite,
)
from .criteria import evaluate_acceptance
from .audit import record_snapshot, get_history


class PlanEngine:
    """Stateful engine for executing a plan table.

    Instantiate with a plan definition and execution state, perform
    operations, then persist the updated state.
    """

    def __init__(self, plan: PlanDefinition, state: ExecutionState):
        self.plan = plan
        self.state = state

    # --- State queries ---

    def get_plan_state(self) -> PlanState:
        """Full execution state with affordances for every row and cell."""
        row_states = [self.get_row_state(ri) for ri in range(self.plan.num_rows)]

        # Compute next_actions: actionable cells across the entire plan
        next_actions = []
        for rs in row_states:
            for cs in rs.cells:
                for action in cs.available_actions:
                    next_actions.append({
                        "action": action,
                        "row": cs.row,
                        "col": cs.col,
                        "row_id": rs.row_id,
                        "column_name": cs.column_name,
                        "description": _action_description(action, rs.row_id, cs.column_name),
                    })

        return PlanState(
            cr_id=self.plan.cr_id,
            status=self.state.status,
            columns=[c.to_dict() for c in self.plan.columns],
            rows=row_states,
            next_actions=next_actions,
        )

    def get_row_state(self, row: int) -> RowState:
        """Compute the full state of a single row."""
        row_id = f"{self.plan.cr_id}-EI-{row + 1}"
        gated, gated_by = self._check_gating(row)

        cells = []
        for ci, col_def in enumerate(self.plan.columns):
            cs = self._compute_cell_state(row, ci, gated)
            cells.append(cs)

        # Acceptance criteria
        acceptance = None
        for ci, col_def in enumerate(self.plan.columns):
            if is_auto_executed(col_def.type):
                acceptance = evaluate_acceptance(self.plan, self.state, row, ci)
                break

        return RowState(
            row=row,
            row_id=row_id,
            gated=gated,
            gated_by=gated_by,
            cells=cells,
            acceptance=acceptance,
        )

    def get_history(self, row: int) -> list[dict]:
        """Audit trail for a row, newest first."""
        return [s.to_dict() for s in get_history(self.state, row)]

    # --- Mutations ---

    def start_execution(self, actor: str) -> PlanState:
        """Initialize execution state. Idempotent if already started."""
        if self.state.status == "not-started":
            self.state.status = "in-progress"
            self.state.started_at = _now()
        return self.get_plan_state()

    def fill_cell(self, row: int, col: int, value: str, actor: str) -> FillResult:
        """Fill an executable cell (free-text, choice-list)."""
        error = self._validate_cell_action(row, col, "fill")
        if error:
            return FillResult(ok=False, error=error)

        col_def = self.plan.columns[col]

        # Validate choice-list values
        if is_choice_list(col_def.type) and col_def.choices:
            if value and value not in col_def.choices:
                return FillResult(
                    ok=False,
                    error=f"Invalid choice '{value}'. Options: {col_def.choices}",
                )

        timestamp = _now()
        self.state.set_cell(row, col, value, timestamp, actor)
        reverted = self._cascade_revert(row, col, timestamp, actor)
        snapshot = record_snapshot(self.plan, self.state, row, actor, timestamp)
        self._update_status()

        return FillResult(
            ok=True,
            row_state=self.get_row_state(row),
            reverted_cells=reverted,
            snapshot=snapshot,
        )

    def sign_cell(self, row: int, col: int, actor: str) -> FillResult:
        """Sign a signature cell."""
        error = self._validate_cell_action(row, col, "sign")
        if error:
            return FillResult(ok=False, error=error)

        timestamp = _now()
        sig_value = f"{actor} \u2014 {timestamp}"
        self.state.set_cell(row, col, sig_value, timestamp, actor)
        reverted = self._cascade_revert(row, col, timestamp, actor)
        snapshot = record_snapshot(self.plan, self.state, row, actor, timestamp)
        self._update_status()

        return FillResult(
            ok=True,
            row_state=self.get_row_state(row),
            reverted_cells=reverted,
            snapshot=snapshot,
        )

    def mark_na(self, row: int, col: int, actor: str) -> FillResult:
        """Mark a cross-reference cell as N/A."""
        error = self._validate_cell_action(row, col, "mark_na")
        if error:
            return FillResult(ok=False, error=error)

        timestamp = _now()
        self.state.set_cell(row, col, "N/A", timestamp, actor)
        reverted = self._cascade_revert(row, col, timestamp, actor)
        snapshot = record_snapshot(self.plan, self.state, row, actor, timestamp)
        self._update_status()

        return FillResult(
            ok=True,
            row_state=self.get_row_state(row),
            reverted_cells=reverted,
            snapshot=snapshot,
        )

    def initiate_issue(
        self, row: int, col: int, actor: str, issue_type: str = "ER"
    ) -> FillResult:
        """Create a child issue reference in a cross-reference cell."""
        error = self._validate_cell_action(row, col, "initiate_issue")
        if error:
            return FillResult(ok=False, error=error)

        # Generate issue ID from the CR and row
        issue_id = f"{self.plan.cr_id}-{issue_type}-{row + 1}"
        ref_value = json.dumps({
            "id": issue_id,
            "status": "draft",
            "type": issue_type,
        })

        timestamp = _now()
        self.state.set_cell(row, col, ref_value, timestamp, actor)
        reverted = self._cascade_revert(row, col, timestamp, actor)
        snapshot = record_snapshot(self.plan, self.state, row, actor, timestamp)
        self._update_status()

        return FillResult(
            ok=True,
            row_state=self.get_row_state(row),
            reverted_cells=reverted,
            snapshot=snapshot,
        )

    # --- Internal logic ---

    def _validate_cell_action(self, row: int, col: int, action: str) -> str | None:
        """Validate that an action can be performed on a cell. Returns error or None."""
        if row < 0 or row >= self.plan.num_rows:
            return f"Row {row} out of range (0-{self.plan.num_rows - 1})"
        if col < 0 or col >= self.plan.num_cols:
            return f"Column {col} out of range (0-{self.plan.num_cols - 1})"

        col_def = self.plan.columns[col]

        if not is_executable(col_def.type):
            return f"Column {col} ({col_def.name}) is not executable (type: {col_def.type})"

        # Check row gating
        gated, gated_by = self._check_gating(row)
        if gated:
            return f"Row {row} is gated by unmet prerequisites: {', '.join(gated_by)}"

        # Check sequential locking
        if self._is_seq_locked(row, col):
            order = self.plan.executable_column_order()
            pos = order.index(col)
            blocking_col = order[pos - 1] if pos > 0 else order[0]
            blocking_name = self.plan.columns[blocking_col].name
            return f"Column {col} ({col_def.name}) is sequentially locked: complete {blocking_name} (col {blocking_col}) first"

        # Action-specific validation
        if action in ("mark_na", "initiate_issue") and not is_cross_ref(col_def.type):
            return f"{action} is only valid for cross-reference columns"

        if action == "sign" and not is_signature(col_def.type):
            return f"sign is only valid for signature columns"

        if action == "fill" and is_signature(col_def.type):
            return "Use sign_cell() for signature columns"

        return None

    def _check_gating(self, row: int) -> tuple[bool, list[str]]:
        """Check if a row is gated by prerequisite dependencies.

        Returns (is_gated, list_of_blocking_row_ids).
        """
        gated_by = []
        for ci, col_def in enumerate(self.plan.columns):
            if not is_prerequisite(col_def.type):
                continue
            deps = _parse_prereqs(self.plan.rows[row][ci])
            for dep_ri in deps:
                if dep_ri < 0 or dep_ri >= self.plan.num_rows:
                    continue
                # Find the acceptance criteria column for the dep row
                ac_col = None
                for aci, ac_def in enumerate(self.plan.columns):
                    if is_auto_executed(ac_def.type):
                        ac_col = aci
                        break
                if ac_col is None:
                    continue
                result = evaluate_acceptance(self.plan, self.state, dep_ri, ac_col)
                if not result.passed:
                    gated_by.append(f"{self.plan.cr_id}-EI-{dep_ri + 1}")
        return bool(gated_by), gated_by

    def _is_seq_locked(self, row: int, col: int) -> bool:
        """Check if a cell is sequentially locked (upstream cell empty)."""
        if not self.plan.sequential_execution:
            return False
        col_def = self.plan.columns[col]
        if not is_executable(col_def.type):
            return False
        order = self.plan.executable_column_order()
        if col not in order:
            return False
        pos = order.index(col)
        if pos == 0:
            return False  # first executable column is never locked
        for i in range(pos):
            if self.state.get_cell(row, order[i]) == "":
                return True
        return False

    def _cascade_revert(
        self, row: int, col: int, timestamp: str, actor: str
    ) -> list[dict]:
        """If sequential execution is enabled, clear all executable cells
        to the right of the changed cell in this row.

        Returns list of reverted cell descriptors.
        """
        if not self.plan.sequential_execution:
            return []
        order = self.plan.executable_column_order()
        if col not in order:
            return []
        pos = order.index(col)
        reverted = []
        for i in range(pos + 1, len(order)):
            ci = order[i]
            old_val = self.state.get_cell(row, ci)
            if old_val:
                self.state.clear_cell(row, ci)
                reverted.append({
                    "row": row,
                    "col": ci,
                    "column_name": self.plan.columns[ci].name,
                    "old_value": old_val,
                })
        return reverted

    def _compute_cell_state(self, row: int, col: int, row_gated: bool) -> CellState:
        """Compute the full state of a single cell."""
        col_def = self.plan.columns[col]
        value = self.state.get_cell(row, col)
        exe = is_executable(col_def.type)
        auto = is_auto_executed(col_def.type)

        # Determine status and display value
        status = "empty"
        display_value = value
        locked_reason = None
        actions: list[str] = []

        if auto:
            # Auto-executed: show acceptance criteria result
            result = evaluate_acceptance(self.plan, self.state, row, col)
            status = "pass" if result.passed else "pending"
            display_value = "PASS" if result.passed else ""
        elif not exe:
            # Non-executable: show authoring value
            if is_prerequisite(col_def.type):
                deps = _parse_prereqs(self.plan.rows[row][col])
                if deps:
                    display_value = ", ".join(
                        f"{self.plan.cr_id}-EI-{d + 1}" for d in deps
                    )
                else:
                    display_value = "N/A"
            else:
                display_value = self.plan.rows[row][col]
            status = "static"
        elif row_gated:
            status = "gated"
            locked_reason = "Row has unmet prerequisites"
        elif self._is_seq_locked(row, col):
            status = "locked"
            order = self.plan.executable_column_order()
            pos = order.index(col)
            for i in range(pos):
                if self.state.get_cell(row, order[i]) == "":
                    blocking = self.plan.columns[order[i]]
                    locked_reason = f"Sequential: complete {blocking.name} first"
                    break
        elif value == "":
            status = "empty"
            actions = _available_actions(col_def)
        elif value == "N/A":
            status = "na"
            display_value = "N/A"
        else:
            status = "filled"
            # Format display value for special types
            if is_cross_ref(col_def.type):
                display_value = _format_cross_ref(value)
            elif is_signature(col_def.type):
                status = "signed"

            # Allow re-fill for editable types
            actions = _available_actions(col_def)

        return CellState(
            row=row,
            col=col,
            column_name=col_def.name,
            column_type=col_def.type,
            value=value,
            display_value=display_value,
            status=status,
            locked_reason=locked_reason,
            available_actions=actions,
        )

    def _update_status(self):
        """Update overall execution status based on cell state."""
        if self.state.status == "not-started":
            self.state.status = "in-progress"
            if not self.state.started_at:
                self.state.started_at = _now()

        # Check if all rows pass acceptance criteria
        all_pass = True
        for ri in range(self.plan.num_rows):
            for ci, col_def in enumerate(self.plan.columns):
                if is_auto_executed(col_def.type):
                    result = evaluate_acceptance(self.plan, self.state, ri, ci)
                    if not result.passed:
                        all_pass = False
                        break
            if not all_pass:
                break
        if all_pass and self.plan.num_rows > 0:
            self.state.status = "completed"
        elif self.state.status == "completed":
            # Reverted from completed (e.g. cascade revert)
            self.state.status = "in-progress"


# --- Helpers ---

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _parse_prereqs(val: str) -> list[int]:
    """Parse prerequisite cell value to list of row indices."""
    if not val:
        return []
    try:
        arr = json.loads(val)
        if isinstance(arr, list):
            return [int(x) for x in arr]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return []


def _format_cross_ref(val: str) -> str:
    """Format a cross-reference value for display."""
    if val == "N/A":
        return "N/A"
    try:
        ref = json.loads(val)
        return f"{ref['id']} ({ref['status']})"
    except (json.JSONDecodeError, TypeError, KeyError):
        return val


def _available_actions(col_def: ColumnDef) -> list[str]:
    """Determine what actions can be performed on a cell based on its type."""
    if is_signature(col_def.type):
        return ["sign"]
    if is_cross_ref(col_def.type):
        return ["mark_na", "initiate_issue"]
    if is_executable(col_def.type):
        return ["fill"]
    return []


def _action_description(action: str, row_id: str, col_name: str) -> str:
    """Human/agent-readable description of an available action."""
    descriptions = {
        "fill": f"Enter {col_name} for {row_id}",
        "sign": f"Sign {col_name} for {row_id}",
        "mark_na": f"Mark {col_name} as N/A for {row_id}",
        "initiate_issue": f"Initiate issue for {col_name} in {row_id}",
    }
    return descriptions.get(action, f"{action} on {col_name} for {row_id}")
