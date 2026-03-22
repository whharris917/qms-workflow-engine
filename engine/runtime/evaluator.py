"""Unified expression evaluator.

All conditions — proceed gates, visibility rules, acceptance criteria,
affordance guards — use the same expression tree schema.

Wraps engine/criteria.py for acceptance-specific leaves and adds
field-level and table-level conditions.
"""

from __future__ import annotations

from typing import Any


def evaluate(expr: dict, data: dict) -> tuple[bool, str]:
    """Evaluate a boolean expression tree against workflow state.

    Args:
        expr: Expression dict — either a composite {op, conditions} or a leaf {type, ...}.
        data: The workflow state dict.

    Returns:
        (passed, reason) tuple.
    """
    if not expr:
        return True, "(empty expression) = True"

    # Composite: AND / OR
    op = expr.get("op")
    if op:
        conditions = expr.get("conditions", [])
        if not conditions:
            return True, f"{op}(empty) = True"

        results = [evaluate(c, data) for c in conditions]

        if op == "AND":
            passed = all(r[0] for r in results)
            detail = " AND ".join(f"({r[1]})" for r in results)
            return passed, f"AND({detail}) = {passed}"
        elif op == "OR":
            passed = any(r[0] for r in results)
            detail = " OR ".join(f"({r[1]})" for r in results)
            return passed, f"OR({detail}) = {passed}"
        elif op == "NOT":
            # NOT takes a single condition (first in list)
            if conditions:
                inner_passed, inner_reason = evaluate(conditions[0], data)
                return not inner_passed, f"NOT({inner_reason}) = {not inner_passed}"
            return True, "NOT(empty) = True"
        else:
            return False, f"unknown op: {op}"

    # Leaf conditions
    return _evaluate_leaf(expr, data)


def _evaluate_leaf(expr: dict, data: dict) -> tuple[bool, str]:
    """Evaluate a leaf condition."""
    cond_type = expr.get("type", "")

    if cond_type == "field_truthy":
        key = expr.get("key", "")
        val = data.get(key)
        passed = bool(val)
        return passed, f"{key} truthy: {passed}"

    if cond_type == "field_equals":
        key = expr.get("key", "")
        expected = expr.get("value")
        val = data.get(key)
        passed = val == expected
        return passed, f"{key} == {expected!r}: {passed}"

    if cond_type == "field_not_null":
        key = expr.get("key", "")
        val = data.get(key)
        passed = val is not None
        return passed, f"{key} not null: {passed}"

    if cond_type == "set_membership":
        key = expr.get("key", "")
        set_ref = expr.get("set_ref", "")
        val = data.get(key)
        # The option set is resolved by the runtime before evaluation
        member_set = data.get(f"__option_set_{set_ref}", set())
        passed = val in member_set
        return passed, f"{key} in {set_ref}: {passed}"

    if cond_type == "table_has_columns":
        table = data.get("table", {})
        cols = table.get("columns", []) if isinstance(table, dict) else []
        passed = len(cols) > 0
        return passed, f"table has columns: {passed}"

    if cond_type == "table_has_rows":
        table = data.get("table", {})
        rows = table.get("rows", []) if isinstance(table, dict) else []
        passed = len(rows) > 0
        return passed, f"table has rows: {passed}"

    if cond_type == "provider_state":
        return _evaluate_provider(expr, data)

    return False, f"unknown condition type: {cond_type}"


def _evaluate_provider(expr: dict, data: dict) -> tuple[bool, str]:
    """Evaluate a condition against cached external provider state.

    Fail-closed: returns False when the provider is unavailable.
    """
    from .providers import registry

    provider_id = expr.get("provider", "")
    provider = registry.get(provider_id)
    if not provider:
        return False, f"unknown provider: {provider_id}"

    cached = data.get(f"_provider_cache_{provider_id}")
    if cached is None:
        return False, f"provider '{provider_id}' state unavailable"

    condition = expr.get("condition", {})
    bindings = data.get(f"_provider_bindings_{provider_id}", {})

    return provider.evaluate(bindings, cached, condition)


def check_visibility(visible_when: dict | None, data: dict) -> bool:
    """Evaluate a field's visible_when condition.

    Supports both the modern expression tree format ({type: ..., key: ...} or
    {op: ..., conditions: [...]}) and the legacy format ({key: value}).
    """
    if not visible_when:
        return True
    # Modern expression tree format — delegate to the unified evaluator
    if "type" in visible_when or "op" in visible_when:
        passed, _ = evaluate(visible_when, data)
        return passed
    # Legacy format: {field_key: expected_value}
    for key, expected in visible_when.items():
        val = data.get(key)
        if expected == "not_null":
            if val is None:
                return False
        elif val != expected:
            return False
    return True
