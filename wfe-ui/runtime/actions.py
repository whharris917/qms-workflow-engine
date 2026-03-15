"""Unified action dispatcher.

All state mutations flow through here. Each action type has a handler
function that validates input, mutates the data dict in place, and
returns the rendered page or an error.
"""

from __future__ import annotations

import json

from .schema import WorkflowDef
from .evaluator import evaluate, check_visibility
from .renderer import render_page, _load_engine


def dispatch(defn: WorkflowDef, data: dict, workflow_id: str, body: dict) -> dict:
    """Process a POST action. Mutates *data* in place.

    Returns the rendered page dict on success, or {"error": msg} on failure.
    """
    action = body.get("action")

    if action == "restart":
        return _restart(defn, data, workflow_id)

    if action == "set_field":
        return _set_field(defn, data, workflow_id, body)

    if action == "proceed":
        return _proceed(defn, data, workflow_id, body)

    if action == "go_back":
        return _go_back(defn, data, workflow_id)

    if action == "go_to":
        return _go_to(defn, data, workflow_id, body)

    if action == "submit":
        return _submit(defn, data, workflow_id)

    # List actions
    if action in ("list_add", "list_edit", "list_remove", "list_reorder", "list_select"):
        return _list_action(defn, data, workflow_id, body, action)

    # Table structural actions
    if action in _TABLE_ACTIONS:
        return _TABLE_ACTIONS[action](defn, data, workflow_id, body)

    # Table execution actions
    if action == "cell_action":
        return _cell_action(defn, data, workflow_id, body)

    if action == "complete":
        return _complete_execution(defn, data, workflow_id)

    return {"error": f"Unknown action: {action}"}


def _restart(defn: WorkflowDef, data: dict, workflow_id: str) -> dict:
    from . import _build_default_data
    fresh = _build_default_data(defn)
    data.clear()
    data.update(fresh)
    return render_page(defn, data, workflow_id)


def _set_field(defn: WorkflowDef, data: dict, workflow_id: str, body: dict) -> dict:
    field_key = body.get("field", "")
    value = body.get("value")

    # Find the field definition
    fdef = None
    for fd in defn.all_fields.values():
        if fd.key == field_key:
            fdef = fd
            break
    if fdef is None:
        return {"error": f"Unknown field: {field_key}"}

    ftype = fdef.type

    if ftype == "boolean":
        if value is not True and value is not False:
            return {"error": f"Invalid value for {fdef.label}. Must be true or false."}
        data[field_key] = value
    elif ftype == "select":
        options = _get_raw_options(defn, fdef, data)
        if options and value not in options:
            return {"error": f"Invalid value for {fdef.label}. Choose: {', '.join(str(o) for o in options)}"}
        data[field_key] = value
    else:  # text
        data[field_key] = value if value else None

    # Process side effects
    if fdef.side_effects:
        for effect in fdef.side_effects:
            when = effect.get("when")
            if when:
                passed, _ = evaluate(when, data)
                if passed:
                    for k, v in effect.get("set", {}).items():
                        data[k] = v

    return render_page(defn, data, workflow_id)


def _get_raw_options(defn: WorkflowDef, fdef, data: dict = None) -> list[str]:
    """Get raw option values (without annotations) for validation."""
    # Dynamic options take priority
    if fdef.dynamic_options and data:
        source_key = fdef.dynamic_options.get("source_key", "")
        mapping = fdef.dynamic_options.get("mapping", {})
        source_val = data.get(source_key)
        if source_val and str(source_val) in mapping:
            return mapping[str(source_val)]
        return fdef.dynamic_options.get("default", [])

    if fdef.options:
        return fdef.options
    if fdef.options_from:
        return defn.option_sets.get(fdef.options_from, [])
    return []


def _proceed(defn: WorkflowDef, data: dict, workflow_id: str, body: dict = None) -> dict:
    node_id = data["node"]
    node = defn.nodes.get(node_id)
    if node_id not in data["completed_nodes"]:
        data["completed_nodes"].append(node_id)

    # Check for explicit target (from proceed definition or body)
    target = None
    if body:
        target = body.get("target")
    if not target and node and node.proceed:
        target = node.proceed.target

    if target and target in defn.node_ids:
        data["node"] = target
    else:
        # Default: next sequential node
        node_ids = defn.node_ids
        idx = node_ids.index(node_id)
        if idx >= len(node_ids) - 1:
            return {"error": "Already at the final node."}
        data["node"] = node_ids[idx + 1]

    # Check if destination node allows auto-advance (pause=False)
    dest_node = defn.nodes.get(data["node"])
    if dest_node and not dest_node.pause:
        # Auto-advance if gate passes (or no gate)
        if dest_node.proceed:
            gate = dest_node.proceed.gate
            if gate:
                from .evaluator import evaluate
                passed, _ = evaluate(gate, data)
            else:
                passed = True
            if passed:
                return _proceed(defn, data, workflow_id)

    return render_page(defn, data, workflow_id)


def _go_back(defn: WorkflowDef, data: dict, workflow_id: str) -> dict:
    node_id = data["node"]
    node_ids = defn.node_ids
    idx = node_ids.index(node_id)
    if idx <= 0:
        return {"error": "Already at the first node."}
    data["node"] = node_ids[idx - 1]
    return render_page(defn, data, workflow_id)


def _go_to(defn: WorkflowDef, data: dict, workflow_id: str, body: dict) -> dict:
    target = body.get("node", "")
    if target not in defn.node_ids:
        return {"error": f"Unknown node: {target}"}
    data["node"] = target
    return render_page(defn, data, workflow_id)


def _submit(defn: WorkflowDef, data: dict, workflow_id: str) -> dict:
    node_id = data["node"]
    node = defn.nodes.get(node_id)
    if node_id not in data["completed_nodes"]:
        data["completed_nodes"].append(node_id)

    # If this is a review→execution transition, initialize the engine
    node_ids = defn.node_ids
    idx = node_ids.index(node_id)
    if idx < len(node_ids) - 1:
        next_node = defn.nodes.get(node_ids[idx + 1])
        if next_node and next_node.execution and "table" in data and not data.get("execution"):
            engine = _load_engine(data)
            engine.start_execution("claude")
            data["execution"] = engine.state.to_dict()
        data["node"] = node_ids[idx + 1]

    return render_page(defn, data, workflow_id)


# ---------------------------------------------------------------------------
# List actions
# ---------------------------------------------------------------------------


def _list_action(defn, data, workflow_id, body, action):
    """Handle list structural operations."""
    list_key = body.get("list_key", "")

    # Find the list definition in the current node
    node_id = data["node"]
    node = defn.nodes.get(node_id)
    if not node:
        return {"error": "Invalid node."}
    list_def = node.lists.get(list_key)
    if not list_def:
        return {"error": f"Unknown list: {list_key}"}

    items = data.setdefault(list_key, [])

    if action == "list_add":
        item = {}
        for fkey, fld in list_def.item_schema.items():
            val = body.get(fkey, "")
            if fld.required and not val:
                return {"error": f"{fkey} is required."}
            if fld.options and val and val not in fld.options:
                return {"error": f"Invalid value for {fkey}. Choose: {', '.join(fld.options)}"}
            item[fkey] = val
        items.append(item)
        # Auto-focus new item if focus enabled
        if list_def.focus:
            data[f"_focused_{list_key}"] = len(items) - 1
        return render_page(defn, data, workflow_id)

    if action == "list_select":
        idx = body.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            return {"error": "Invalid index."}
        data[f"_focused_{list_key}"] = idx
        return render_page(defn, data, workflow_id)

    if action == "list_edit":
        idx = body.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            return {"error": "Invalid index."}
        item = items[idx]
        for fkey, fld in list_def.item_schema.items():
            if fkey in body and body[fkey] != f"<{fkey}>":
                val = body[fkey]
                if fld.options and val and val not in fld.options:
                    return {"error": f"Invalid value for {fkey}. Choose: {', '.join(fld.options)}"}
                item[fkey] = val
        return render_page(defn, data, workflow_id)

    if action == "list_remove":
        idx = body.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            return {"error": "Invalid index."}
        items.pop(idx)
        # Adjust focus
        focused_key = f"_focused_{list_key}"
        if data.get(focused_key) is not None:
            if data[focused_key] == idx:
                data[focused_key] = None
            elif data[focused_key] > idx:
                data[focused_key] -= 1
        return render_page(defn, data, workflow_id)

    if action == "list_reorder":
        idx = body.get("index")
        direction = body.get("direction", "up")
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            return {"error": "Invalid index."}
        focused_key = f"_focused_{list_key}"
        if direction == "up" and idx > 0:
            items[idx], items[idx-1] = items[idx-1], items[idx]
            if data.get(focused_key) == idx:
                data[focused_key] = idx - 1
            elif data.get(focused_key) == idx - 1:
                data[focused_key] = idx
        elif direction == "down" and idx < len(items) - 1:
            items[idx], items[idx+1] = items[idx+1], items[idx]
            if data.get(focused_key) == idx:
                data[focused_key] = idx + 1
            elif data.get(focused_key) == idx + 1:
                data[focused_key] = idx
        return render_page(defn, data, workflow_id)

    return {"error": f"Unknown list action: {action}"}


# ---------------------------------------------------------------------------
# Table structural actions
# ---------------------------------------------------------------------------

def _ensure_table(data: dict) -> dict:
    """Ensure data has table structure."""
    if "table" not in data:
        data["table"] = {"columns": [], "rows": [], "properties": {"sequential_execution": False}}
    t = data["table"]
    t.setdefault("columns", [])
    t.setdefault("rows", [])
    t.setdefault("properties", {"sequential_execution": False})
    return t


def _add_column(defn, data, workflow_id, body):
    t = _ensure_table(data)
    name = body.get("name", "").strip()
    col_type = body.get("type", "")
    if not name:
        return {"error": "Column name is required."}
    valid_types = list(defn.column_types.keys()) if defn.column_types else []
    if valid_types and col_type not in valid_types:
        return {"error": f"Invalid column type. Choose: {', '.join(valid_types)}"}
    t["columns"].append({"name": name, "type": col_type})
    for row in t["rows"]:
        row.append("")
    return render_page(defn, data, workflow_id)


def _add_row(defn, data, workflow_id, body):
    t = _ensure_table(data)
    if not t["columns"]:
        return {"error": "Add at least one column before adding rows."}
    t["rows"].append([""] * len(t["columns"]))
    return render_page(defn, data, workflow_id)


def _set_cell(defn, data, workflow_id, body):
    t = _ensure_table(data)
    ri, ci = body.get("row"), body.get("col")
    value = body.get("value", "")
    if not isinstance(ri, int) or not isinstance(ci, int):
        return {"error": "row and col must be integers."}
    if ri < 0 or ri >= len(t["rows"]):
        return {"error": f"Row {ri} out of range."}
    if ci < 0 or ci >= len(t["columns"]):
        return {"error": f"Column {ci} out of range."}
    t["rows"][ri][ci] = value
    return render_page(defn, data, workflow_id)


def _rename_column(defn, data, workflow_id, body):
    t = _ensure_table(data)
    ci = body.get("col")
    name = body.get("name", "").strip()
    if not isinstance(ci, int) or ci < 0 or ci >= len(t["columns"]):
        return {"error": "Invalid column index."}
    if not name:
        return {"error": "Column name is required."}
    t["columns"][ci]["name"] = name
    return render_page(defn, data, workflow_id)


def _set_column_type(defn, data, workflow_id, body):
    t = _ensure_table(data)
    ci = body.get("col")
    col_type = body.get("type", "")
    if not isinstance(ci, int) or ci < 0 or ci >= len(t["columns"]):
        return {"error": "Invalid column index."}
    valid_types = list(defn.column_types.keys()) if defn.column_types else []
    if valid_types and col_type not in valid_types:
        return {"error": f"Invalid column type. Choose: {', '.join(valid_types)}"}
    t["columns"][ci]["type"] = col_type
    return render_page(defn, data, workflow_id)


def _remove_column(defn, data, workflow_id, body):
    t = _ensure_table(data)
    ci = body.get("col")
    if not isinstance(ci, int) or ci < 0 or ci >= len(t["columns"]):
        return {"error": "Invalid column index."}
    t["columns"].pop(ci)
    for row in t["rows"]:
        if ci < len(row):
            row.pop(ci)
    return render_page(defn, data, workflow_id)


def _remove_row(defn, data, workflow_id, body):
    t = _ensure_table(data)
    ri = body.get("row")
    if not isinstance(ri, int) or ri < 0 or ri >= len(t["rows"]):
        return {"error": "Invalid row index."}
    t["rows"].pop(ri)
    return render_page(defn, data, workflow_id)


def _set_choices(defn, data, workflow_id, body):
    t = _ensure_table(data)
    ci = body.get("col")
    choices = body.get("choices")
    if not isinstance(ci, int) or ci < 0 or ci >= len(t["columns"]):
        return {"error": "Invalid column index."}
    col = t["columns"][ci]
    if col["type"] not in ("ex-choice-list", "choice-list"):
        return {"error": f"Column {ci} ({col['name']}) is not a choice-list column."}
    if not isinstance(choices, list) or not all(isinstance(c, str) for c in choices):
        return {"error": "choices must be an array of strings."}
    col["choices"] = choices
    return render_page(defn, data, workflow_id)


def _set_rule(defn, data, workflow_id, body):
    t = _ensure_table(data)
    ci = body.get("col")
    rule = body.get("rule")
    if not isinstance(ci, int) or ci < 0 or ci >= len(t["columns"]):
        return {"error": "Invalid column index."}
    col = t["columns"][ci]
    if col["type"] != "ae-acceptance-criteria":
        return {"error": f"Column {ci} ({col['name']}) is not an acceptance-criteria column."}
    if not isinstance(rule, dict) or rule.get("op") not in ("AND", "OR"):
        return {"error": "rule must be an object with 'op' (AND/OR) and 'conditions'."}
    col["rule"] = rule
    return render_page(defn, data, workflow_id)


def _set_prerequisites(defn, data, workflow_id, body):
    t = _ensure_table(data)
    ri, ci = body.get("row"), body.get("col")
    prereqs = body.get("prerequisites")
    if not isinstance(ri, int) or not isinstance(ci, int):
        return {"error": "row and col must be integers."}
    if ri < 0 or ri >= len(t["rows"]):
        return {"error": f"Row {ri} out of range."}
    if ci < 0 or ci >= len(t["columns"]):
        return {"error": f"Column {ci} out of range."}
    col = t["columns"][ci]
    if col["type"] != "ne-prerequisite":
        return {"error": f"Column {ci} ({col['name']}) is not a prerequisite column."}
    if not isinstance(prereqs, list):
        return {"error": "prerequisites must be an array of row indices."}
    for p in prereqs:
        if not isinstance(p, int) or p < 0 or p >= len(t["rows"]):
            return {"error": f"Invalid prerequisite row index: {p}."}
        if p == ri:
            return {"error": "A row cannot be a prerequisite of itself."}
    t["rows"][ri][ci] = json.dumps(prereqs)
    return render_page(defn, data, workflow_id)


def _set_property(defn, data, workflow_id, body):
    t = _ensure_table(data)
    key = body.get("key", "")
    value = body.get("value")
    if key == "sequential_execution":
        if value is not True and value is not False:
            return {"error": "sequential_execution must be true or false."}
        t["properties"]["sequential_execution"] = value
        return render_page(defn, data, workflow_id)
    return {"error": f"Unknown property: {key}"}


_TABLE_ACTIONS = {
    "add_column": _add_column,
    "add_row": _add_row,
    "set_cell": _set_cell,
    "rename_column": _rename_column,
    "set_column_type": _set_column_type,
    "remove_column": _remove_column,
    "remove_row": _remove_row,
    "set_choices": _set_choices,
    "set_rule": _set_rule,
    "set_prerequisites": _set_prerequisites,
    "set_property": _set_property,
}


# ---------------------------------------------------------------------------
# Execution engine actions
# ---------------------------------------------------------------------------

def _cell_action(defn, data, workflow_id, body):
    engine = _load_engine(data)
    row, col = body.get("row"), body.get("col")
    cell_action = body.get("cell_action", "")
    if not isinstance(row, int) or not isinstance(col, int):
        return {"error": "row and col must be integers."}

    if cell_action == "fill":
        result = engine.fill_cell(row, col, body.get("value", ""), "claude")
    elif cell_action == "amend":
        # Amend dispatches to the appropriate engine method based on column type
        from engine.types import is_signature, is_cross_ref
        col_def = engine.plan.columns[col]
        if is_signature(col_def.type):
            result = engine.sign_cell(row, col, "claude", is_resign=True)
        elif is_cross_ref(col_def.type):
            # For cross-refs, amend can be mark_na or initiate_issue
            sub_action = body.get("sub_action", "mark_na")
            if sub_action == "initiate_issue":
                result = engine.initiate_issue(
                    row, col, "claude", body.get("issue_type", "ER"), is_amend=True)
            else:
                result = engine.mark_na(row, col, "claude", is_amend=True)
        else:
            result = engine.fill_cell(row, col, body.get("value", ""), "claude", is_amend=True)
    elif cell_action == "re-sign":
        result = engine.sign_cell(row, col, "claude", is_resign=True)
    elif cell_action == "sign":
        result = engine.sign_cell(row, col, "claude")
    elif cell_action == "mark_na":
        result = engine.mark_na(row, col, "claude")
    elif cell_action == "initiate_issue":
        result = engine.initiate_issue(row, col, "claude", body.get("issue_type", "ER"))
    else:
        return {"error": f"Unknown cell action: {cell_action}"}

    if not result.ok:
        return {"error": result.error}

    data["execution"] = engine.state.to_dict()

    # Auto-advance to done only if the destination node allows it (pause=False)
    if engine.state.status == "completed":
        node_id = data["node"]
        node_ids = defn.node_ids
        idx = node_ids.index(node_id)
        if idx < len(node_ids) - 1:
            next_node = defn.nodes.get(node_ids[idx + 1])
            if next_node and not next_node.pause:
                if node_id not in data["completed_nodes"]:
                    data["completed_nodes"].append(node_id)
                data["node"] = node_ids[idx + 1]

    return render_page(defn, data, workflow_id)


def _complete_execution(defn, data, workflow_id):
    engine = _load_engine(data)
    if engine.state.status != "completed":
        return {"error": "Not all acceptance criteria have passed."}
    node_id = data["node"]
    if node_id not in data["completed_nodes"]:
        data["completed_nodes"].append(node_id)
    node_ids = defn.node_ids
    idx = node_ids.index(node_id)
    if idx < len(node_ids) - 1:
        data["node"] = node_ids[idx + 1]
    return render_page(defn, data, workflow_id)
