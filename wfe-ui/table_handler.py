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

from engine import PlanEngine
from engine.types import ColumnDef, PlanDefinition, ExecutionState, is_choice_list

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
# Execution engine bridge
# ---------------------------------------------------------------------------


def _build_plan_def(data: dict) -> PlanDefinition:
    """Construct a PlanDefinition from the in-memory table data."""
    columns = [ColumnDef.from_dict(c) for c in data["columns"]]
    return PlanDefinition(
        cr_id="WF",  # synthetic — no CR file on disk
        columns=columns,
        rows=data["rows"],
        table_properties={
            "sequentialExecution": data["properties"].get("sequential_execution", False),
        },
    )


def _load_engine(data: dict):
    """Hydrate a PlanEngine from the table data + persisted execution state."""
    plan = _build_plan_def(data)
    exec_state = data.get("execution")
    if exec_state:
        state = ExecutionState.from_dict(exec_state)
    else:
        state = ExecutionState(cr_id="WF")
    return PlanEngine(plan, state)


def _execution_progress(engine) -> dict:
    """Compute execution progress stats."""
    from engine.types import EXECUTABLE_TYPES
    ps = engine.get_plan_state()
    total_cells = 0
    filled_cells = 0
    completed_rows = 0
    for rs in ps.rows:
        if rs.acceptance and rs.acceptance.passed:
            completed_rows += 1
        for cs in rs.cells:
            if cs.column_type in EXECUTABLE_TYPES:
                total_cells += 1
                if cs.value:
                    filled_cells += 1
    return {
        "total_rows": len(ps.rows),
        "completed_rows": completed_rows,
        "total_cells": total_cells,
        "filled_cells": filled_cells,
    }


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
        cols = data["columns"]
        rows = data["rows"]
        col_indices = list(range(len(cols)))
        col_labels = [c["name"] for c in cols]

        # -- Add column --
        # Build type options with descriptions from YAML catalog
        type_options_info = [
            {"value": t, "label": info.get("label", t),
             "category": info.get("category", ""),
             "description": info.get("description", "")}
            for t, info in _COLUMN_TYPES.items()
        ]
        affordances.append({
            "id": n, "label": "Add column",
            "method": "POST", "url": f"{api}/add_column",
            "body": {"name": "<name>", "type": "<type>"},
            "parameters": {
                "name": {},
                "type": {
                    "options": _VALID_COLUMN_TYPES,
                    "descriptions": type_options_info,
                },
            },
        })
        n += 1

        # -- Add row (only if columns exist) --
        if cols:
            affordances.append({
                "id": n, "label": "Add row",
                "method": "POST", "url": f"{api}/add_row",
                "body": {},
            })
            n += 1

        # -- Column management (parameterized) --
        if cols:
            affordances.append({
                "id": n, "label": "Rename column",
                "method": "POST", "url": f"{api}/rename_column",
                "body": {"col": "<col>", "name": "<name>"},
                "parameters": {
                    "col": {"options": col_indices, "labels": col_labels},
                    "name": {},
                },
            })
            n += 1

            affordances.append({
                "id": n, "label": "Set column type",
                "method": "POST", "url": f"{api}/set_column_type",
                "body": {"col": "<col>", "type": "<type>"},
                "parameters": {
                    "col": {"options": col_indices, "labels": col_labels},
                    "type": {"options": _VALID_COLUMN_TYPES},
                },
            })
            n += 1

            affordances.append({
                "id": n, "label": "Remove column",
                "method": "POST", "url": f"{api}/remove_column",
                "body": {"col": "<col>"},
                "parameters": {
                    "col": {"options": col_indices, "labels": col_labels},
                },
            })
            n += 1

            # -- Choice-list column management --
            choice_cols = [(i, c) for i, c in enumerate(cols) if c["type"] in ("ex-choice-list", "choice-list")]
            if choice_cols:
                choice_indices = [i for i, _ in choice_cols]
                choice_labels = [c["name"] for _, c in choice_cols]
                affordances.append({
                    "id": n, "label": "Set choices for column",
                    "method": "POST", "url": f"{api}/set_choices",
                    "body": {"col": "<col>", "choices": "<choices>"},
                    "parameters": {
                        "col": {"options": choice_indices, "labels": choice_labels},
                        "choices": {"description": "Array of valid option strings, e.g. [\"Pass\", \"Fail\", \"N/A\"]"},
                    },
                })
                n += 1

            # -- Acceptance criteria rule management --
            ae_cols = [(i, c) for i, c in enumerate(cols) if c["type"] == "ae-acceptance-criteria"]
            if ae_cols:
                ae_indices = [i for i, _ in ae_cols]
                ae_labels = [c["name"] for _, c in ae_cols]
                # Build available conditions based on executable columns
                exec_col_info = [
                    {"index": i, "name": c["name"], "type": c["type"]}
                    for i, c in enumerate(cols)
                    if c["type"] in ("ex-free-text", "ex-choice-list", "ex-cross-reference",
                                     "ex-signature", "free-text", "choice-list",
                                     "cross-reference", "signature")
                ]
                affordances.append({
                    "id": n, "label": "Set acceptance rule for column",
                    "method": "POST", "url": f"{api}/set_rule",
                    "body": {"col": "<col>", "rule": "<rule>"},
                    "parameters": {
                        "col": {"options": ae_indices, "labels": ae_labels},
                        "rule": {
                            "description": "Boolean expression tree. Structure: {\"op\": \"AND\"|\"OR\", \"conditions\": [...]}. "
                                           "Leaf conditions: {\"type\": \"all-executed\"} checks all executable columns are filled; "
                                           "{\"type\": \"column\", \"column\": <col_index>, \"operator\": \"is-filled\"|\"is-signed\"|\"equals\"|\"ref-status\", \"value\": \"...\"} "
                                           "checks a specific column. Example: {\"op\": \"AND\", \"conditions\": [{\"type\": \"all-executed\"}]}",
                            "executable_columns": exec_col_info,
                        },
                    },
                })
                n += 1

            # -- Prerequisite cell management --
            prereq_cols = [(i, c) for i, c in enumerate(cols) if c["type"] == "ne-prerequisite"]
            if prereq_cols and rows:
                prereq_col_indices = [i for i, _ in prereq_cols]
                prereq_col_labels = [c["name"] for _, c in prereq_cols]
                row_ids = [f"EI-{i+1}" for i in range(len(rows))]
                affordances.append({
                    "id": n, "label": "Set prerequisites for cell",
                    "method": "POST", "url": f"{api}/set_prerequisites",
                    "body": {"row": "<row>", "col": "<col>", "prerequisites": "<prerequisites>"},
                    "parameters": {
                        "row": {"options": list(range(len(rows))), "labels": row_ids},
                        "col": {"options": prereq_col_indices, "labels": prereq_col_labels},
                        "prerequisites": {"description": "Array of row indices that must pass acceptance before this row can execute, e.g. [0, 1]"},
                    },
                })
                n += 1

        # -- Cell editing (parameterized) --
        if cols and rows:
            row_indices = list(range(len(rows)))
            affordances.append({
                "id": n, "label": "Set cell",
                "method": "POST", "url": f"{api}/set_cell",
                "body": {"row": "<row>", "col": "<col>", "value": "<value>"},
                "parameters": {
                    "row": {"options": row_indices},
                    "col": {"options": col_indices, "labels": col_labels},
                    "value": {},
                },
            })
            n += 1

            affordances.append({
                "id": n, "label": "Remove row",
                "method": "POST", "url": f"{api}/remove_row",
                "body": {"row": "<row>"},
                "parameters": {
                    "row": {"options": row_indices},
                },
            })
            n += 1

        # -- Table properties --
        seq = data["properties"].get("sequential_execution", False)
        affordances.append({
            "id": n,
            "label": f"Set sequential execution (current: {json.dumps(seq)})",
            "method": "POST", "url": f"{api}/set_property",
            "body": {"key": "sequential_execution", "value": "<value>"},
            "parameters": {
                "value": {"options": [True, False]},
            },
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

        # Proceed to Execution
        affordances.append({
            "id": n, "label": "Proceed to Execution",
            "method": "POST", "url": f"{api}/submit",
            "body": {},
        })
        n += 1

    elif node == "executing":
        engine = _load_engine(data)
        ps = engine.get_plan_state()

        # Dynamic cell affordances from engine
        for act in ps.next_actions:
            action = act["action"]
            row = act["row"]
            col = act["col"]
            col_name = act["column_name"]
            row_id = act["row_id"]

            cell_body = {"row": row, "col": col, "cell_action": action}
            params = {}

            if action == "fill":
                cell_body["value"] = "<value>"
                col_def = engine.plan.columns[col]
                if is_choice_list(col_def.type) and col_def.choices:
                    params["value"] = {"options": col_def.choices}
                else:
                    params["value"] = {}
                label = f"Fill {col_name} for {row_id}"
            elif action == "sign":
                label = f"Sign {col_name} for {row_id}"
            elif action == "mark_na":
                label = f"Mark {col_name} as N/A for {row_id}"
            elif action == "initiate_issue":
                cell_body["issue_type"] = "<issue_type>"
                params["issue_type"] = {"options": ["VAR", "ER"]}
                label = f"Initiate issue for {col_name} in {row_id}"
            else:
                label = act.get("description", action)

            a = {
                "id": n, "label": label,
                "method": "POST", "url": f"{api}/cell_action",
                "body": cell_body,
            }
            if params:
                a["parameters"] = params
            affordances.append(a)
            n += 1

        # Complete gate
        if ps.status == "completed":
            affordances.append({
                "id": n, "label": "Complete Execution",
                "method": "POST", "url": f"{api}/complete",
                "body": {},
            })
            n += 1

        # Go back to review
        affordances.append({
            "id": n, "label": "Go back to Review",
            "method": "POST", "url": f"{api}/go_back",
            "body": {},
        })
        n += 1

    elif node == "done":
        affordances.append({
            "id": n, "label": "Go back to Execution",
            "method": "POST", "url": f"{api}/go_back",
            "body": {},
        })
        n += 1

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

    state = {
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
    }

    # Add execution state when in executing/done nodes
    if node in ("executing", "done") and data.get("execution"):
        engine = _load_engine(data)
        ps = engine.get_plan_state()
        state["plan_status"] = ps.status
        state["progress"] = _execution_progress(engine)
        state["execution_table"] = {
            "columns": ps.columns,
            "rows": [r.to_dict() for r in ps.rows],
        }

    return {
        "state": state,
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

    # -- set_choices (choice-list column options) --
    if action == "set_choices":
        ci = body.get("col")
        choices = body.get("choices")
        if not isinstance(ci, int) or ci < 0 or ci >= len(data["columns"]):
            return {"error": "Invalid column index."}
        col = data["columns"][ci]
        if col["type"] not in ("ex-choice-list", "choice-list"):
            return {"error": f"Column {ci} ({col['name']}) is not a choice-list column."}
        if not isinstance(choices, list):
            return {"error": "choices must be an array of strings."}
        if not all(isinstance(c, str) for c in choices):
            return {"error": "All choices must be strings."}
        col["choices"] = choices
        return render_node(data, workflow_id)

    # -- set_rule (acceptance criteria rule) --
    if action == "set_rule":
        ci = body.get("col")
        rule = body.get("rule")
        if not isinstance(ci, int) or ci < 0 or ci >= len(data["columns"]):
            return {"error": "Invalid column index."}
        col = data["columns"][ci]
        if col["type"] != "ae-acceptance-criteria":
            return {"error": f"Column {ci} ({col['name']}) is not an acceptance-criteria column."}
        if not isinstance(rule, dict):
            return {"error": "rule must be an object with 'op' and 'conditions' keys."}
        if rule.get("op") not in ("AND", "OR"):
            return {"error": "rule.op must be 'AND' or 'OR'."}
        if not isinstance(rule.get("conditions"), list):
            return {"error": "rule.conditions must be an array."}
        col["rule"] = rule
        return render_node(data, workflow_id)

    # -- set_prerequisites (prerequisite cell dependencies) --
    if action == "set_prerequisites":
        ri = body.get("row")
        ci = body.get("col")
        prereqs = body.get("prerequisites")
        if not isinstance(ri, int) or not isinstance(ci, int):
            return {"error": "row and col must be integers."}
        if ri < 0 or ri >= len(data["rows"]):
            return {"error": f"Row {ri} out of range (0-{len(data['rows'])-1})."}
        if ci < 0 or ci >= len(data["columns"]):
            return {"error": f"Column {ci} out of range (0-{len(data['columns'])-1})."}
        col = data["columns"][ci]
        if col["type"] != "ne-prerequisite":
            return {"error": f"Column {ci} ({col['name']}) is not a prerequisite column."}
        if not isinstance(prereqs, list):
            return {"error": "prerequisites must be an array of row indices."}
        for p in prereqs:
            if not isinstance(p, int) or p < 0 or p >= len(data["rows"]):
                return {"error": f"Invalid prerequisite row index: {p}. Valid range: 0-{len(data['rows'])-1}."}
            if p == ri:
                return {"error": "A row cannot be a prerequisite of itself."}
        # Store as JSON array string (matches edit_plan.html format)
        data["rows"][ri][ci] = json.dumps(prereqs)
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
        if node == "executing":
            data["node"] = "review"
            return render_node(data, workflow_id)
        if node == "done":
            data["node"] = "executing"
            if "executing" in data["completed_nodes"]:
                data["completed_nodes"].remove("executing")
            return render_node(data, workflow_id)
        return {"error": "Cannot go back from this node."}

    # -- submit (review → executing) --
    if action == "submit":
        if node != "review":
            return {"error": "Can only proceed to execution from the Review node."}
        if "review" not in data["completed_nodes"]:
            data["completed_nodes"].append("review")
        # Initialize execution engine from table data
        engine = _load_engine(data)
        engine.start_execution("claude")
        data["execution"] = engine.state.to_dict()
        data["node"] = "executing"
        return render_node(data, workflow_id)

    # -- cell_action (fill, sign, mark_na, initiate_issue) --
    if action == "cell_action":
        if node != "executing":
            return {"error": "Can only execute cells from the Execution node."}
        engine = _load_engine(data)
        row = body.get("row")
        col = body.get("col")
        cell_action = body.get("cell_action", "")

        if not isinstance(row, int) or not isinstance(col, int):
            return {"error": "row and col must be integers."}

        if cell_action == "fill":
            result = engine.fill_cell(row, col, body.get("value", ""), "claude")
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

        # Auto-advance to done if all acceptance criteria pass
        if engine.state.status == "completed":
            if "executing" not in data["completed_nodes"]:
                data["completed_nodes"].append("executing")
            data["node"] = "done"

        return render_node(data, workflow_id)

    # -- complete --
    if action == "complete":
        if node != "executing":
            return {"error": "Can only complete from the Execution node."}
        engine = _load_engine(data)
        if engine.state.status != "completed":
            return {"error": "Not all acceptance criteria have passed."}
        if "executing" not in data["completed_nodes"]:
            data["completed_nodes"].append("executing")
        data["node"] = "done"
        return render_node(data, workflow_id)

    return {"error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Resource-oriented endpoint translation
# ---------------------------------------------------------------------------

# Actions that take no body parameters (just dispatch)
_SIMPLE_ACTIONS = {"proceed", "go_back", "submit", "restart", "complete"}

# Actions that pass the body through (parameters in body)
_BODY_ACTIONS = {
    "add_column", "add_row", "set_cell", "rename_column",
    "set_column_type", "remove_column", "remove_row", "set_property",
    "set_choices", "set_rule", "set_prerequisites",
    "cell_action",
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
    if action == "set_choices":
        return f"Set choices for column {body.get('col')}"
    if action == "set_rule":
        return f"Set acceptance rule for column {body.get('col')}"
    if action == "set_prerequisites":
        return f"Set prerequisites for cell [{body.get('row')}, {body.get('col')}]"
    if action == "cell_action":
        cell_act = body.get("cell_action", "?")
        row = body.get("row", "?")
        col = body.get("col", "?")
        return f"{cell_act} on cell [{row}, {col}]"
    return action
