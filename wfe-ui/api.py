"""REST API blueprint for plan execution.

Thin wrapper over engine.PlanEngine — all business logic lives in the engine.
Responses are agent-friendly: self-describing state with affordances.

Execution state is ephemeral (in-memory only). It resets on server restart
or when the client calls start_execution again.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, request, abort

from engine import PlanEngine
from engine.persistence import load_plan
from engine.types import ExecutionState

api = Blueprint("api", __name__, url_prefix="/api")

DATA_DIR = Path(__file__).resolve().parent / "data"

# In-memory execution engines, keyed by cr_id.
# Cleared on server restart; reset per-CR on start_execution.
_engines: dict[str, PlanEngine] = {}


def _get_engine(cr_id: str) -> PlanEngine:
    """Return the in-memory engine for a CR, or 404 if not started."""
    engine = _engines.get(cr_id)
    if engine is None:
        abort(404, description=f"No active execution for {cr_id}. Call start first.")
    return engine


@api.route("/cr/<cr_id>/plan")
def get_plan(cr_id):
    """Get the plan definition (authoring data)."""
    plan = load_plan(DATA_DIR, cr_id)
    if plan is None:
        abort(404)
    return {
        "ok": True,
        "data": {
            "cr_id": plan.cr_id,
            "columns": [c.to_dict() for c in plan.columns],
            "rows": plan.rows,
            "table_properties": plan.table_properties,
        },
    }


@api.route("/cr/<cr_id>/execution")
def get_execution(cr_id):
    """Get full execution state with affordances for every row and cell."""
    engine = _get_engine(cr_id)
    ps = engine.get_plan_state()
    return {"ok": True, "data": ps.to_dict()}


@api.route("/cr/<cr_id>/execution/row/<int:row>")
def get_row(cr_id, row):
    """Get a single row's execution state."""
    engine = _get_engine(cr_id)
    if row < 0 or row >= engine.plan.num_rows:
        abort(404, description=f"Row {row} out of range")
    rs = engine.get_row_state(row)
    return {"ok": True, "data": rs.to_dict()}


@api.route("/cr/<cr_id>/execution/start", methods=["POST"])
def start_execution(cr_id):
    """Start a fresh execution session. Always resets state."""
    body = request.get_json(silent=True) or {}
    actor = body.get("actor", "unknown")
    plan = load_plan(DATA_DIR, cr_id)
    if plan is None:
        abort(404, description=f"CR {cr_id} not found")
    engine = PlanEngine(plan, ExecutionState(cr_id=cr_id))
    ps = engine.start_execution(actor)
    _engines[cr_id] = engine
    return {"ok": True, "data": ps.to_dict()}


@api.route("/cr/<cr_id>/execution/cell", methods=["POST"])
def execute_cell(cr_id):
    """Fill, sign, or mark a cell. Unified endpoint for all cell mutations.

    Body: {"row": 0, "col": 2, "action": "fill", "value": "Done", "actor": "claude"}
    Actions: fill, sign, mark_na, initiate_issue
    """
    body = request.get_json()
    if not body:
        return {"ok": False, "error": "Request body required"}, 400

    row = body.get("row")
    col = body.get("col")
    action = body.get("action")
    actor = body.get("actor", "unknown")
    value = body.get("value", "")

    if row is None or col is None or not action:
        return {"ok": False, "error": "row, col, and action are required"}, 400

    engine = _get_engine(cr_id)

    if action == "fill":
        result = engine.fill_cell(row, col, value, actor)
    elif action == "sign":
        result = engine.sign_cell(row, col, actor)
    elif action == "mark_na":
        result = engine.mark_na(row, col, actor)
    elif action == "initiate_issue":
        issue_type = body.get("issue_type", "ER")
        result = engine.initiate_issue(row, col, actor, issue_type)
    else:
        return {"ok": False, "error": f"Unknown action: {action}"}, 400

    if result.ok:
        # Include full plan state so the client can re-render everything
        ps = engine.get_plan_state()
        return {
            "ok": True,
            "result": result.to_dict(),
            "plan_state": ps.to_dict(),
        }
    else:
        return {"ok": False, "error": result.error}, 422


@api.route("/cr/<cr_id>/execution/history/<int:row>")
def get_history(cr_id, row):
    """Audit trail for a row, newest first."""
    engine = _get_engine(cr_id)
    if row < 0 or row >= engine.plan.num_rows:
        abort(404, description=f"Row {row} out of range")
    history = engine.get_history(row)
    return {"ok": True, "data": history}
