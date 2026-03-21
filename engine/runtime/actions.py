"""Unified action dispatcher.

All state mutations flow through here. Each action type has a handler
function that validates input, mutates the data dict in place, and
returns the rendered page or an error.
"""

from __future__ import annotations

import json

from .schema import WorkflowDef
from .evaluator import evaluate, check_visibility
from .renderer import render_page as _render_page_impl
from .affordances import _load_engine

# Instance context — set at dispatch() entry so internal functions can call
# render_page() without threading instance_id through every signature.
_current_instance_id: str | None = None


def render_page(defn, data, workflow_id):
    """Wrapper that injects the current instance_id into render calls."""
    return _render_page_impl(defn, data, workflow_id, _current_instance_id)


def dispatch(defn: WorkflowDef, data: dict, workflow_id: str, body: dict,
             instance_id: str | None = None) -> dict:
    """Process a POST action. Mutates *data* in place.

    Returns the rendered page dict on success, or {"error": msg} on failure.
    """
    global _current_instance_id
    _current_instance_id = instance_id
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

    if action == "switch_branch":
        return _switch_branch(defn, data, workflow_id, body)

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

    if action == "provider_action":
        return _provider_action(defn, data, workflow_id, body)

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

    # --- Fork activation: node has fork instead of proceed ---
    if node and node.fork:
        return _activate_fork(defn, data, workflow_id, node)

    # --- Branch-aware proceed: inside a fork ---
    fork_state = data.get("fork_state")
    if fork_state:
        return _branch_proceed(defn, data, workflow_id, fork_state)

    # --- Standard proceed ---
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

    return _enter_node(defn, data, workflow_id)


def _enter_node(defn: WorkflowDef, data: dict, workflow_id: str, _depth: int = 0) -> dict:
    """Handle arrival at a new node — auto-routing and auto-advance.

    Called after any navigation that lands on a new node. Handles:
    1. Router nodes: evaluate conditions and advance to matching target
    2. Auto-advance (pause=False): proceed if gate passes
    """
    if _depth > 20:
        return {"error": "Navigation depth limit exceeded (possible infinite loop)."}

    dest_node = defn.nodes.get(data["node"])
    if not dest_node:
        return render_page(defn, data, workflow_id)

    # Router: evaluate routes and auto-advance
    if dest_node.router:
        return _route(defn, data, workflow_id, dest_node, _depth)

    # Auto-advance (pause=False) with proceed gate
    if not dest_node.pause and dest_node.proceed:
        gate = dest_node.proceed.gate
        if gate:
            passed, _ = evaluate(gate, data)
        else:
            passed = True
        if passed:
            if data["node"] not in data["completed_nodes"]:
                data["completed_nodes"].append(data["node"])
            target = dest_node.proceed.target
            if target and target in defn.node_ids:
                data["node"] = target
            else:
                node_ids = defn.node_ids
                idx = node_ids.index(data["node"])
                if idx < len(node_ids) - 1:
                    data["node"] = node_ids[idx + 1]
            return _enter_node(defn, data, workflow_id, _depth + 1)

    return render_page(defn, data, workflow_id)


def _route(defn: WorkflowDef, data: dict, workflow_id: str,
           node, _depth: int = 0) -> dict:
    """Evaluate a router node and advance to the first matching target."""
    if node.id not in data["completed_nodes"]:
        data["completed_nodes"].append(node.id)

    for route in node.router:
        if route.when:
            passed, _ = evaluate(route.when, data)
            if not passed:
                continue
        # Match found (or default route with no when)
        if route.target not in defn.node_ids:
            return {"error": f"Router target '{route.target}' not found."}
        data["node"] = route.target
        return _enter_node(defn, data, workflow_id, _depth + 1)

    return {"error": "Router: no matching route and no default."}


def _activate_fork(defn: WorkflowDef, data: dict, workflow_id: str,
                   node) -> dict:
    """Activate parallel branches from a fork node."""
    if node.id not in data["completed_nodes"]:
        data["completed_nodes"].append(node.id)

    fork_def = node.fork
    branches = {}
    first_branch_id = None
    for bid, bdef in fork_def.branches.items():
        if not bdef.nodes:
            return {"error": f"Fork branch '{bid}' has no nodes."}
        for nid in bdef.nodes:
            if nid not in defn.node_ids:
                return {"error": f"Fork branch '{bid}' references unknown node '{nid}'."}
        branches[bid] = {
            "node": bdef.nodes[0],
            "completed_nodes": [],
            "completed": False,
        }
        if first_branch_id is None:
            first_branch_id = bid

    data["fork_state"] = {
        "fork_node": node.id,
        "merge_node": fork_def.merge,
        "active_branch": first_branch_id,
        "branches": branches,
    }
    data["node"] = branches[first_branch_id]["node"]

    # Enter the first branch's first node (may be a router, etc.)
    return _enter_node(defn, data, workflow_id)


def _branch_proceed(defn: WorkflowDef, data: dict, workflow_id: str,
                    fork_state: dict) -> dict:
    """Proceed within a fork branch."""
    active_bid = fork_state["active_branch"]
    branch = fork_state["branches"][active_bid]
    node_id = data["node"]
    fork_def = defn.nodes[fork_state["fork_node"]].fork

    # Mark current node completed (in branch tracking)
    if node_id not in branch["completed_nodes"]:
        branch["completed_nodes"].append(node_id)
    if node_id not in data["completed_nodes"]:
        data["completed_nodes"].append(node_id)

    # Find position in branch sequence
    branch_nodes = fork_def.branches[active_bid].nodes
    try:
        idx = branch_nodes.index(node_id)
    except ValueError:
        return {"error": f"Node '{node_id}' not in branch '{active_bid}'."}

    if idx < len(branch_nodes) - 1:
        # More nodes in this branch
        next_node = branch_nodes[idx + 1]
        branch["node"] = next_node
        data["node"] = next_node
        return _enter_node(defn, data, workflow_id)

    # Branch complete
    branch["completed"] = True
    branch["node"] = None

    # Check if all branches are complete
    all_done = all(b["completed"] for b in fork_state["branches"].values())
    if all_done:
        # Advance to merge node, clear fork state
        merge_node = fork_state["merge_node"]
        del data["fork_state"]
        data["node"] = merge_node
        return _enter_node(defn, data, workflow_id)

    # Auto-switch to next incomplete branch
    for bid, b in fork_state["branches"].items():
        if not b["completed"]:
            fork_state["active_branch"] = bid
            data["node"] = b["node"]
            return render_page(defn, data, workflow_id)

    # Shouldn't reach here, but safety net
    return render_page(defn, data, workflow_id)


def _switch_branch(defn: WorkflowDef, data: dict, workflow_id: str,
                   body: dict) -> dict:
    """Switch to a different branch within a fork."""
    fork_state = data.get("fork_state")
    if not fork_state:
        return {"error": "Not in a fork."}

    target_branch = body.get("branch", "")
    if target_branch not in fork_state["branches"]:
        return {"error": f"Unknown branch: {target_branch}"}

    branch = fork_state["branches"][target_branch]
    if branch["completed"]:
        return {"error": f"Branch '{target_branch}' is already completed."}

    fork_state["active_branch"] = target_branch
    data["node"] = branch["node"]
    return render_page(defn, data, workflow_id)


def _go_back(defn: WorkflowDef, data: dict, workflow_id: str) -> dict:
    node_id = data["node"]

    # Fork-aware: if at first node in branch, go back to fork node
    fork_state = data.get("fork_state")
    if fork_state:
        active_bid = fork_state["active_branch"]
        fork_def = defn.nodes[fork_state["fork_node"]].fork
        branch_nodes = fork_def.branches[active_bid].nodes
        if node_id == branch_nodes[0]:
            # At start of branch — can't go back further within branch
            return {"error": "Already at the first node in this branch."}
        # Go back within the branch
        idx = branch_nodes.index(node_id)
        prev_node = branch_nodes[idx - 1]
        fork_state["branches"][active_bid]["node"] = prev_node
        data["node"] = prev_node
        return render_page(defn, data, workflow_id)

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
    if col["type"] != "ex-choice-list":
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


def _provider_action(defn, data, workflow_id, body):
    """Route an action to an external state provider."""
    from .providers import registry, resolve_bindings, ProviderUnavailableError

    provider_id = body.get("provider", "")
    provider = registry.get(provider_id)
    if not provider:
        return {"error": f"Unknown provider: {provider_id}"}

    # Resolve bindings from workflow-level provider config
    pdef = defn.providers.get(provider_id)
    if not pdef:
        return {"error": f"Provider '{provider_id}' not declared in this workflow."}

    bindings = resolve_bindings(pdef.bindings, data)
    action_name = body.get("provider_action", "")
    params = {k: v for k, v in body.items()
              if k not in ("action", "provider", "provider_action")}

    try:
        result = provider.execute(bindings, action_name, params)
    except ProviderUnavailableError as e:
        return {"error": f"Provider '{provider_id}' unavailable: {e.detail}"}

    if not result.get("ok", False):
        return {"error": result.get("error", "Provider action failed.")}

    # Invalidate cached state so next render re-queries
    data.pop(f"_provider_cache_{provider_id}", None)

    return render_page(defn, data, workflow_id)
