"""Execute Implementation Plan workflow handler.

Wraps the PlanEngine in the handler protocol so agents can drive execution
through the same affordance-based interface used for CR authoring and plan
building.  All cell logic (fill, sign, sequential locking, gating, cascade
revert, acceptance criteria) is delegated to the engine package.

Interface consumed by app.py:
    WORKFLOW_TITLE                          -> str
    VALID_RESOURCES                         -> set[str]
    default_data()                          -> dict (fresh state)
    render_node(data, workflow_id)          -> page dict
    process_action(data, workflow_id, body) -> page dict | error dict
    resolve_resource(resource, body)        -> (internal_body, acted_label) | None
"""

from pathlib import Path

import yaml

from engine import PlanEngine
from engine.persistence import load_plan
from engine.types import ExecutionState, is_choice_list

# ---------------------------------------------------------------------------
# Load YAML definition
# ---------------------------------------------------------------------------

_YAML_PATH = Path(__file__).parent / "data" / "agent_execute_plan.yaml"
with open(_YAML_PATH) as _f:
    _DEF = yaml.safe_load(_f)

_NODES = list(_DEF["nodes"].keys())
_LIFECYCLE = _DEF["lifecycle_banner"]

_NODE_INFO = {
    nid: {"title": n["title"], "instruction": n["instruction"]}
    for nid, n in _DEF["nodes"].items()
}
_NODE_TO_LIFECYCLE = {
    nid: n["lifecycle_label"]
    for nid, n in _DEF["nodes"].items()
}

WORKFLOW_TITLE = "Execute Implementation Plan"

DATA_DIR = Path(__file__).resolve().parent / "data"

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def default_data() -> dict:
    """Return a fresh workflow state."""
    return {
        "node": "loading",
        "completed_nodes": [],
        "cr_id": None,
        "actor": "claude",
        "execution": None,
    }


def _ensure_data(data: dict) -> dict:
    if "node" not in data:
        return default_data()
    data.setdefault("completed_nodes", [])
    data.setdefault("cr_id", None)
    data.setdefault("actor", "claude")
    data.setdefault("execution", None)
    return data


def _load_engine(data: dict):
    """Hydrate a PlanEngine from persisted data. Returns (engine, error_str)."""
    cr_id = data.get("cr_id")
    if not cr_id:
        return None, "No CR selected"
    plan = load_plan(DATA_DIR, cr_id)
    if plan is None:
        return None, f"CR {cr_id} not found or has no plan"
    exec_state = data.get("execution")
    if exec_state:
        state = ExecutionState.from_dict(exec_state)
    else:
        state = ExecutionState(cr_id=cr_id)
    return PlanEngine(plan, state), None


def _available_crs() -> list[str]:
    """Scan data dir for CRs that have a valid implementation plan."""
    crs = []
    for p in sorted(DATA_DIR.glob("CR-*.json")):
        plan = load_plan(DATA_DIR, p.stem)
        if plan and plan.columns and plan.rows:
            crs.append(p.stem)
    return crs


# ---------------------------------------------------------------------------
# Affordances
# ---------------------------------------------------------------------------


def _build_affordances(data: dict, workflow_id: str) -> list[dict]:
    node = data["node"]
    affordances = []
    n = 1
    api = f"/agent/{workflow_id}"

    if node == "loading":
        # Set CR ID
        available = _available_crs()
        affordances.append({
            "id": n, "label": f"Set CR ID (current: {data.get('cr_id') or 'none'})",
            "method": "POST", "url": f"{api}/set_cr",
            "body": {"value": "<value>"},
            "parameters": {"value": {"options": available}} if available else {},
        })
        n += 1

        # Set actor
        affordances.append({
            "id": n, "label": f"Set Actor (current: {data.get('actor', 'claude')})",
            "method": "POST", "url": f"{api}/set_actor",
            "body": {"value": "<value>"},
        })
        n += 1

        # Start gate: CR must be selected and have a valid plan
        if data.get("cr_id"):
            plan = load_plan(DATA_DIR, data["cr_id"])
            if plan and plan.columns and plan.rows:
                affordances.append({
                    "id": n, "label": "Start Execution",
                    "method": "POST", "url": f"{api}/start",
                    "body": {},
                })
                n += 1

    elif node == "executing":
        engine, err = _load_engine(data)
        if engine:
            ps = engine.get_plan_state()
            # Generate affordances from next_actions
            for act in ps.next_actions:
                action = act["action"]
                row = act["row"]
                col = act["col"]
                col_name = act["column_name"]
                row_id = act["row_id"]

                body = {"row": row, "col": col, "cell_action": action}
                params = {}

                if action == "fill":
                    body["value"] = "<value>"
                    # Add options for choice-list columns
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
                    body["issue_type"] = "<issue_type>"
                    params["issue_type"] = {"options": ["VAR", "ER"]}
                    label = f"Initiate issue for {col_name} in {row_id}"
                else:
                    label = act.get("description", action)

                a = {
                    "id": n, "label": label,
                    "method": "POST", "url": f"{api}/cell_action",
                    "body": body,
                }
                if params:
                    a["parameters"] = params
                affordances.append(a)
                n += 1

            # Complete gate: all acceptance criteria pass
            if ps.status == "completed":
                affordances.append({
                    "id": n, "label": "Complete Execution",
                    "method": "POST", "url": f"{api}/complete",
                    "body": {},
                })
                n += 1

        # Always allow go_back
        affordances.append({
            "id": n, "label": "Go back to Load Plan",
            "method": "POST", "url": f"{api}/go_back",
            "body": {},
        })
        n += 1

    elif node == "completed":
        affordances.append({
            "id": n, "label": "Go back to Execution",
            "method": "POST", "url": f"{api}/go_back",
            "body": {},
        })
        n += 1

        affordances.append({
            "id": n, "label": "Start a new Execution",
            "method": "POST", "url": f"{api}/restart",
            "body": {},
        })
        n += 1

    return affordances


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _progress(engine) -> dict:
    """Compute execution progress stats."""
    ps = engine.get_plan_state()
    total_cells = 0
    filled_cells = 0
    completed_rows = 0

    for rs in ps.rows:
        row_passed = rs.acceptance and rs.acceptance.passed
        if row_passed:
            completed_rows += 1
        for cs in rs.cells:
            if cs.column_type in (
                "ex-free-text", "ex-choice-list", "ex-cross-reference",
                "ex-signature", "free-text", "choice-list",
                "cross-reference", "signature",
            ):
                total_cells += 1
                if cs.value:
                    filled_cells += 1

    return {
        "total_rows": len(ps.rows),
        "completed_rows": completed_rows,
        "total_cells": total_cells,
        "filled_cells": filled_cells,
    }


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
        "cr_id": data.get("cr_id"),
        "actor": data.get("actor", "claude"),
    }

    # Add execution-specific state when engine is available
    engine, _ = _load_engine(data)
    if engine and data.get("execution"):
        ps = engine.get_plan_state()
        state["plan_status"] = ps.status
        state["progress"] = _progress(engine)
        state["table"] = {
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

    # -- set_cr --
    if action == "set_cr":
        if node != "loading":
            return {"error": "Can only set CR from the Loading node."}
        value = body.get("value", "")
        if not value:
            return {"error": "CR ID is required."}
        # Validate CR exists with a plan
        plan = load_plan(DATA_DIR, value)
        if plan is None:
            return {"error": f"CR {value} not found."}
        if not plan.columns or not plan.rows:
            return {"error": f"CR {value} has no implementation plan."}
        data["cr_id"] = value
        data["execution"] = None  # reset any prior execution
        return render_node(data, workflow_id)

    # -- set_actor --
    if action == "set_actor":
        if node != "loading":
            return {"error": "Can only set actor from the Loading node."}
        value = body.get("value", "").strip()
        if not value:
            return {"error": "Actor name is required."}
        data["actor"] = value
        return render_node(data, workflow_id)

    # -- start --
    if action == "start":
        if node != "loading":
            return {"error": "Can only start from the Loading node."}
        engine, err = _load_engine(data)
        if err:
            return {"error": err}
        engine.start_execution(data.get("actor", "claude"))
        data["execution"] = engine.state.to_dict()
        if "loading" not in data["completed_nodes"]:
            data["completed_nodes"].append("loading")
        data["node"] = "executing"
        return render_node(data, workflow_id)

    # -- cell_action --
    if action == "cell_action":
        if node != "executing":
            return {"error": "Can only execute cells from the Execution node."}
        engine, err = _load_engine(data)
        if err:
            return {"error": err}

        row = body.get("row")
        col = body.get("col")
        cell_action = body.get("cell_action", "")
        actor = data.get("actor", "claude")

        if not isinstance(row, int) or not isinstance(col, int):
            return {"error": "row and col must be integers."}

        if cell_action == "fill":
            result = engine.fill_cell(row, col, body.get("value", ""), actor)
        elif cell_action == "sign":
            result = engine.sign_cell(row, col, actor)
        elif cell_action == "mark_na":
            result = engine.mark_na(row, col, actor)
        elif cell_action == "initiate_issue":
            issue_type = body.get("issue_type", "ER")
            result = engine.initiate_issue(row, col, actor, issue_type)
        else:
            return {"error": f"Unknown cell action: {cell_action}"}

        if not result.ok:
            return {"error": result.error}

        data["execution"] = engine.state.to_dict()

        # Auto-advance to completed if all acceptance criteria pass
        if engine.state.status == "completed":
            if "executing" not in data["completed_nodes"]:
                data["completed_nodes"].append("executing")
            data["node"] = "completed"

        return render_node(data, workflow_id)

    # -- complete --
    if action == "complete":
        if node != "executing":
            return {"error": "Can only complete from the Execution node."}
        engine, err = _load_engine(data)
        if err:
            return {"error": err}
        if engine.state.status != "completed":
            return {"error": "Not all acceptance criteria have passed."}
        if "executing" not in data["completed_nodes"]:
            data["completed_nodes"].append("executing")
        data["node"] = "completed"
        return render_node(data, workflow_id)

    # -- go_back --
    if action == "go_back":
        if node == "executing":
            data["node"] = "loading"
            return render_node(data, workflow_id)
        if node == "completed":
            data["node"] = "executing"
            # Remove executing from completed_nodes so we can re-complete
            if "executing" in data["completed_nodes"]:
                data["completed_nodes"].remove("executing")
            return render_node(data, workflow_id)
        return {"error": "Cannot go back from this node."}

    return {"error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Resource-oriented endpoint translation
# ---------------------------------------------------------------------------

_SIMPLE_ACTIONS = {"start", "complete", "go_back", "restart"}
_BODY_ACTIONS = {"set_cr", "set_actor", "cell_action"}

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
        acted_label = _action_label(resource, body)
        return internal, acted_label

    return None


def _action_label(action: str, body: dict) -> str | None:
    """Build a human-readable label describing the action for feedback."""
    if action == "set_cr":
        return f"Set CR ID to {body.get('value', '?')}"
    if action == "set_actor":
        return f"Set Actor to {body.get('value', '?')}"
    if action == "cell_action":
        cell_act = body.get("cell_action", "?")
        row = body.get("row", "?")
        col = body.get("col", "?")
        return f"{cell_act} on cell [{row}, {col}]"
    return action
