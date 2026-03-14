"""Table-based implementation plan workflow handler.

Manages the table data model (columns, rows, cells, properties) for the
create-implementation-plan workflow.  All rendering and action processing
is self-contained — app.py delegates to this module by workflow type.

Interface consumed by app.py:
    default_data()                       -> dict (fresh state)
    render_node(data, workflow_id)       -> page dict
    process_action(data, workflow_id, body) -> page dict | error dict
    resolve_resource(resource, body)     -> (internal_body, acted_label) | None
"""

import json
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Load YAML definition
# ---------------------------------------------------------------------------

_YAML_PATH = Path(__file__).parent / "data" / "agent_create_implementation_plan.yaml"
with open(_YAML_PATH) as _f:
    _DEF = yaml.safe_load(_f)

_NODES = list(_DEF["nodes"].keys())
_LIFECYCLE = _DEF["lifecycle_banner"]
_COLUMN_TYPES = _DEF["column_types"]
_VALID_COLUMN_TYPES = list(_COLUMN_TYPES.keys())

_NODE_INFO = {
    nid: {"title": n["title"], "instruction": n["instruction"]}
    for nid, n in _DEF["nodes"].items()
}
_NODE_TO_LIFECYCLE = {
    nid: n["lifecycle_label"]
    for nid, n in _DEF["nodes"].items()
}

WORKFLOW_TITLE = "Create Implementation Plan"

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def default_data() -> dict:
    """Return a fresh workflow state."""
    return {
        "node": _NODES[0],
        "completed_nodes": [],
        "columns": [],
        "rows": [],
        "properties": {"sequential_execution": False},
    }


def _ensure_data(data: dict) -> dict:
    """Ensure data dict has the expected structure, initializing if needed."""
    if "node" not in data:
        return default_data()
    data.setdefault("completed_nodes", [])
    data.setdefault("columns", [])
    data.setdefault("rows", [])
    data.setdefault("properties", {"sequential_execution": False})
    return data


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _table_summary(data: dict) -> str:
    ncols = len(data["columns"])
    nrows = len(data["rows"])
    return f"{ncols} column{'s' if ncols != 1 else ''}, {nrows} row{'s' if nrows != 1 else ''}"


def _build_affordances(data: dict, workflow_id: str) -> list[dict]:
    """Generate affordances for the current node."""
    node = data["node"]
    affordances = []
    n = 1
    api = f"/agent/{workflow_id}"

    if node == "construction":
        # -- Add column --
        affordances.append({
            "id": n, "label": "Add column",
            "method": "POST", "url": f"{api}/add_column",
            "body": {"name": "<column_name>", "type": "<column_type>"},
            "options": _VALID_COLUMN_TYPES,
        })
        n += 1

        cols = data["columns"]

        # -- Add row (only if columns exist) --
        if cols:
            affordances.append({
                "id": n, "label": "Add row",
                "method": "POST", "url": f"{api}/add_row",
                "body": {},
            })
            n += 1

        # -- Per-column management --
        for ci, col in enumerate(cols):
            affordances.append({
                "id": n,
                "label": f"Rename column {ci} (current: \"{col['name']}\")",
                "method": "POST", "url": f"{api}/rename_column",
                "body": {"col": ci, "name": "<new_name>"},
            })
            n += 1

            affordances.append({
                "id": n,
                "label": f"Set type of column {ci} (current: {col['type']})",
                "method": "POST", "url": f"{api}/set_column_type",
                "body": {"col": ci, "type": "<column_type>"},
                "options": _VALID_COLUMN_TYPES,
            })
            n += 1

            affordances.append({
                "id": n,
                "label": f"Remove column {ci} (\"{col['name']}\")",
                "method": "POST", "url": f"{api}/remove_column",
                "body": {"col": ci},
            })
            n += 1

        # -- Per-cell set --
        rows = data["rows"]
        for ri, row in enumerate(rows):
            for ci, val in enumerate(row):
                col = cols[ci] if ci < len(cols) else {"name": f"col-{ci}"}
                display = json.dumps(val) if val else "null"
                affordances.append({
                    "id": n,
                    "label": f"Set cell [{ri}, {ci}] {col['name']} (current: {display})",
                    "method": "POST", "url": f"{api}/set_cell",
                    "body": {"row": ri, "col": ci, "value": "<value>"},
                })
                n += 1

        # -- Per-row remove --
        for ri in range(len(rows)):
            affordances.append({
                "id": n,
                "label": f"Remove row {ri}",
                "method": "POST", "url": f"{api}/remove_row",
                "body": {"row": ri},
            })
            n += 1

        # -- Table properties --
        seq = data["properties"].get("sequential_execution", False)
        affordances.append({
            "id": n,
            "label": f"Set sequential execution (current: {json.dumps(seq)})",
            "method": "POST", "url": f"{api}/set_property",
            "body": {"key": "sequential_execution", "value": "<value>"},
            "options": [True, False],
        })
        n += 1

        # -- Proceed gate: at least one column and one row --
        if cols and rows:
            proceed_def = _DEF["nodes"]["construction"].get("proceed", {})
            affordances.append({
                "id": n,
                "label": proceed_def.get("label", "Proceed to Review"),
                "method": "POST", "url": f"{api}/proceed",
                "body": {},
            })
            n += 1

    elif node == "review":
        # Navigation
        affordances.append({
            "id": n, "label": "Go back to Table Construction",
            "method": "POST", "url": f"{api}/go_back",
            "body": {},
        })
        n += 1

        # Finalize
        affordances.append({
            "id": n, "label": "Finalize Plan",
            "method": "POST", "url": f"{api}/submit",
            "body": {},
        })
        n += 1

    elif node == "done":
        affordances.append({
            "id": n, "label": "Start a new Implementation Plan",
            "method": "POST", "url": f"{api}/restart",
            "body": {},
        })
        n += 1

    return affordances


def render_node(data: dict, workflow_id: str) -> dict:
    """Render the current workflow state as a JSON-serializable page dict."""
    data = _ensure_data(data)
    node = data["node"]
    info = _NODE_INFO[node]

    lifecycle_current = _NODE_TO_LIFECYCLE.get(node, _LIFECYCLE[0])
    lifecycle_completed = []
    for cn in data["completed_nodes"]:
        lbl = _NODE_TO_LIFECYCLE.get(cn)
        if lbl and lbl not in lifecycle_completed:
            lifecycle_completed.append(lbl)

    affordances = _build_affordances(data, workflow_id)

    return {
        "state": {
            "workflow": WORKFLOW_TITLE,
            "node": node,
            "node_title": info["title"],
            "lifecycle": _LIFECYCLE,
            "lifecycle_current": lifecycle_current,
            "lifecycle_completed": lifecycle_completed,
            "completed_nodes": data["completed_nodes"],
            "table": {
                "columns": data["columns"],
                "rows": data["rows"],
                "properties": data["properties"],
                "summary": _table_summary(data),
            },
        },
        "instructions": info["instruction"],
        "affordances": affordances,
    }


# ---------------------------------------------------------------------------
# Action processing
# ---------------------------------------------------------------------------


def process_action(data: dict, workflow_id: str, body: dict) -> dict:
    """Process a POST action.  Mutates *data* in place.

    Returns the rendered page dict on success, or ``{"error": msg}`` on failure.
    """
    data = _ensure_data(data)
    action = body.get("action")
    node = data["node"]

    # -- restart --
    if action == "restart":
        fresh = default_data()
        data.clear()
        data.update(fresh)
        return render_node(data, workflow_id)

    # -- add_column --
    if action == "add_column":
        name = body.get("name", "").strip()
        col_type = body.get("type", "")
        if not name:
            return {"error": "Column name is required."}
        if col_type not in _VALID_COLUMN_TYPES:
            return {"error": f"Invalid column type. Choose: {', '.join(_VALID_COLUMN_TYPES)}"}
        col = {"name": name, "type": col_type}
        data["columns"].append(col)
        # Extend existing rows with an empty cell
        for row in data["rows"]:
            row.append("")
        return render_node(data, workflow_id)

    # -- add_row --
    if action == "add_row":
        if not data["columns"]:
            return {"error": "Add at least one column before adding rows."}
        ncols = len(data["columns"])
        data["rows"].append([""] * ncols)
        return render_node(data, workflow_id)

    # -- set_cell --
    if action == "set_cell":
        ri = body.get("row")
        ci = body.get("col")
        value = body.get("value", "")
        if not isinstance(ri, int) or not isinstance(ci, int):
            return {"error": "row and col must be integers."}
        if ri < 0 or ri >= len(data["rows"]):
            return {"error": f"Row {ri} out of range (0-{len(data['rows'])-1})."}
        if ci < 0 or ci >= len(data["columns"]):
            return {"error": f"Column {ci} out of range (0-{len(data['columns'])-1})."}
        data["rows"][ri][ci] = value
        return render_node(data, workflow_id)

    # -- rename_column --
    if action == "rename_column":
        ci = body.get("col")
        name = body.get("name", "").strip()
        if not isinstance(ci, int) or ci < 0 or ci >= len(data["columns"]):
            return {"error": f"Invalid column index."}
        if not name:
            return {"error": "Column name is required."}
        data["columns"][ci]["name"] = name
        return render_node(data, workflow_id)

    # -- set_column_type --
    if action == "set_column_type":
        ci = body.get("col")
        col_type = body.get("type", "")
        if not isinstance(ci, int) or ci < 0 or ci >= len(data["columns"]):
            return {"error": "Invalid column index."}
        if col_type not in _VALID_COLUMN_TYPES:
            return {"error": f"Invalid column type. Choose: {', '.join(_VALID_COLUMN_TYPES)}"}
        data["columns"][ci]["type"] = col_type
        return render_node(data, workflow_id)

    # -- remove_column --
    if action == "remove_column":
        ci = body.get("col")
        if not isinstance(ci, int) or ci < 0 or ci >= len(data["columns"]):
            return {"error": "Invalid column index."}
        data["columns"].pop(ci)
        for row in data["rows"]:
            if ci < len(row):
                row.pop(ci)
        return render_node(data, workflow_id)

    # -- remove_row --
    if action == "remove_row":
        ri = body.get("row")
        if not isinstance(ri, int) or ri < 0 or ri >= len(data["rows"]):
            return {"error": "Invalid row index."}
        data["rows"].pop(ri)
        return render_node(data, workflow_id)

    # -- set_property --
    if action == "set_property":
        key = body.get("key", "")
        value = body.get("value")
        if key == "sequential_execution":
            if value is not True and value is not False:
                return {"error": "sequential_execution must be true or false."}
            data["properties"]["sequential_execution"] = value
            return render_node(data, workflow_id)
        return {"error": f"Unknown property: {key}"}

    # -- proceed --
    if action == "proceed":
        if node != "construction":
            return {"error": "Can only proceed from Table Construction."}
        if not data["columns"] or not data["rows"]:
            return {"error": "Table must have at least one column and one row."}
        if "construction" not in data["completed_nodes"]:
            data["completed_nodes"].append("construction")
        data["node"] = "review"
        return render_node(data, workflow_id)

    # -- go_back --
    if action == "go_back":
        if node == "review":
            data["node"] = "construction"
            return render_node(data, workflow_id)
        return {"error": "Cannot go back from this node."}

    # -- submit / finalize --
    if action == "submit":
        if node != "review":
            return {"error": "Can only finalize from the Review node."}
        if "review" not in data["completed_nodes"]:
            data["completed_nodes"].append("review")
        data["node"] = "done"
        return render_node(data, workflow_id)

    return {"error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Resource-oriented endpoint translation
# ---------------------------------------------------------------------------

# Actions that take no body parameters (just dispatch)
_SIMPLE_ACTIONS = {"proceed", "go_back", "submit", "restart"}

# Actions that pass the body through (parameters in body)
_BODY_ACTIONS = {
    "add_column", "add_row", "set_cell", "rename_column",
    "set_column_type", "remove_column", "remove_row", "set_property",
}

VALID_RESOURCES = _SIMPLE_ACTIONS | _BODY_ACTIONS


def resolve_resource(resource: str, body: dict):
    """Translate a resource URL segment + body into (internal_body, acted_label).

    Returns None if the resource is not recognized by this handler.
    """
    if resource in _SIMPLE_ACTIONS:
        return {"action": resource}, None

    if resource in _BODY_ACTIONS:
        internal = dict(body)
        internal["action"] = resource
        # Build a human-readable label for the attempted action
        acted_label = _action_label(resource, body)
        return internal, acted_label

    return None


def _action_label(action: str, body: dict) -> str | None:
    """Build a human-readable label describing the action for feedback."""
    if action == "add_column":
        return f"Add column \"{body.get('name', '')}\" ({body.get('type', '')})"
    if action == "add_row":
        return "Add row"
    if action == "set_cell":
        return f"Set cell [{body.get('row')}, {body.get('col')}]"
    if action == "rename_column":
        return f"Rename column {body.get('col')} to \"{body.get('name', '')}\""
    if action == "set_column_type":
        return f"Set column {body.get('col')} type to {body.get('type', '')}"
    if action == "remove_column":
        return f"Remove column {body.get('col')}"
    if action == "remove_row":
        return f"Remove row {body.get('row')}"
    if action == "set_property":
        return f"Set {body.get('key')} = {body.get('value')}"
    return action
