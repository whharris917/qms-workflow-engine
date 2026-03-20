"""Boolean expression evaluator for acceptance criteria.

Evaluates rules defined as nested AND/OR groups with leaf conditions.
Mirrors the JS evaluateRule/evaluateCondition logic exactly.
"""

from __future__ import annotations

import json

from .types import (
    PlanDefinition,
    ExecutionState,
    AcceptanceResult,
    is_executable,
    is_choice_list,
    is_cross_ref,
    is_signature,
)


def evaluate_acceptance(
    plan: PlanDefinition,
    state: ExecutionState,
    row: int,
    col: int,
) -> AcceptanceResult:
    """Evaluate the acceptance criteria column for a given row."""
    column = plan.columns[col]
    rule = column.rule
    if not rule:
        return AcceptanceResult(passed=True, reason="No rule defined — auto-pass")
    passed, reason = _evaluate_rule(plan, state, rule, row)
    return AcceptanceResult(passed=passed, reason=reason)


def _evaluate_rule(
    plan: PlanDefinition,
    state: ExecutionState,
    rule: dict,
    row: int,
) -> tuple[bool, str]:
    """Evaluate an AND/OR rule group. Returns (passed, reason)."""
    conditions = rule.get("conditions", [])
    op = rule.get("op", "AND")

    if not conditions:
        return True, f"{op}(empty) = True"

    results = []
    for cond in conditions:
        if "op" in cond:
            # Nested group
            passed, reason = _evaluate_rule(plan, state, cond, row)
        else:
            passed, reason = _evaluate_condition(plan, state, cond, row)
        results.append((passed, reason))

    if op == "AND":
        all_pass = all(r[0] for r in results)
        detail = " AND ".join(f"({r[1]})" for r in results)
        return all_pass, f"AND({detail}) = {all_pass}"
    else:
        any_pass = any(r[0] for r in results)
        detail = " OR ".join(f"({r[1]})" for r in results)
        return any_pass, f"OR({detail}) = {any_pass}"


def _evaluate_condition(
    plan: PlanDefinition,
    state: ExecutionState,
    cond: dict,
    row: int,
) -> tuple[bool, str]:
    """Evaluate a leaf condition. Returns (passed, reason)."""
    cond_type = cond.get("type", "")

    if cond_type == "all-executed":
        # Check all executable columns in this row have values
        for ci, col_def in enumerate(plan.columns):
            if not is_executable(col_def.type):
                continue
            val = state.get_cell(row, ci)
            if val == "":
                return False, f"all-executed: col {ci} ({col_def.name}) is empty"
        return True, "all-executed: all filled"

    if cond_type == "column":
        col_idx = cond.get("column")
        if col_idx is None or col_idx >= len(plan.columns):
            return False, f"column condition: invalid column index {col_idx}"

        col_def = plan.columns[col_idx]
        val = state.get_cell(row, col_idx)
        operator = cond.get("operator", "")
        expected = cond.get("value", "")

        if operator == "equals":
            passed = val == expected
            return passed, f"{col_def.name} equals '{expected}': {passed}"

        if operator == "is-filled":
            passed = val != ""
            return passed, f"{col_def.name} is filled: {passed}"

        if operator == "is-signed":
            passed = val != ""
            return passed, f"{col_def.name} is signed: {passed}"

        if operator == "ref-status":
            if not val or val == "N/A":
                return False, f"{col_def.name} ref-status: no reference"
            try:
                ref = json.loads(val)
                actual_status = ref.get("status", "")
                passed = actual_status == expected
                return passed, f"{col_def.name} ref-status '{actual_status}' == '{expected}': {passed}"
            except (json.JSONDecodeError, TypeError):
                passed = val == expected
                return passed, f"{col_def.name} ref-status (raw) == '{expected}': {passed}"

        return False, f"unknown operator: {operator}"

    return False, f"unknown condition type: {cond_type}"
