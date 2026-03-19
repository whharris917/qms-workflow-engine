"""State rendering — builds the page dict from workflow state.

Produces the {state, instructions, affordances} page dict that the
observer UI expects. All affordance generation happens here.
"""

from __future__ import annotations

import json

from .schema import WorkflowDef, FieldDef, NodeDef
from .evaluator import evaluate, check_visibility

# Re-use existing helpers
import sys
import os
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from utils import trunc, field as make_field

from engine import PlanEngine
from engine.types import ColumnDef, PlanDefinition, ExecutionState, is_choice_list


def _build_lifecycle(defn: WorkflowDef) -> list:
    """Build a topology-aware lifecycle structure for the banner.

    Returns a list of items, each either:
      {"type": "node", "id": "...", "title": "..."}
      {"type": "router", "id": "...", "title": "...", "targets": [{"label": "...", "id": "..."}]}
      {"type": "fork", "id": "...", "title": "...",
       "branches": [{"label": "...", "nodes": [{"id": "...", "title": "..."}...]}...],
       "merge": {"id": "...", "title": "..."}}
    """
    # Identify nodes claimed by forks
    claimed = set()
    merge_of = {}  # merge_id -> fork_id
    for nid, nd in defn.nodes.items():
        if nd.fork:
            for bdef in nd.fork.branches.values():
                for bnid in bdef.nodes:
                    claimed.add(bnid)
            if nd.fork.merge:
                merge_of[nd.fork.merge] = nid

    items = []
    for nid, nd in defn.nodes.items():
        if nid in claimed or nid in merge_of:
            continue

        if nd.router:
            targets = []
            for route in nd.router:
                tnode = defn.nodes.get(route.target)
                targets.append({
                    "label": _cond_label(route.when),
                    "id": route.target,
                    "title": tnode.title if tnode else route.target,
                })
            items.append({"type": "router", "id": nid, "title": nd.title, "targets": targets})

        elif nd.fork:
            branches = []
            for bid, bdef in nd.fork.branches.items():
                bnodes = []
                for bnid in bdef.nodes:
                    bnode = defn.nodes.get(bnid)
                    bnodes.append({"id": bnid, "title": bnode.title if bnode else bnid})
                branches.append({"label": bdef.label, "nodes": bnodes})
            merge_node = defn.nodes.get(nd.fork.merge)
            items.append({
                "type": "fork", "id": nid, "title": nd.title,
                "branches": branches,
                "merge": {"id": nd.fork.merge, "title": merge_node.title if merge_node else nd.fork.merge},
            })

        else:
            items.append({"type": "node", "id": nid, "title": nd.title})

    return items


def _cond_label(when: dict | None) -> str:
    """Short label for a router condition."""
    if not when:
        return "default"
    if when.get("type") == "field_equals":
        return f"{when.get('key')} = {when.get('value')}"
    if when.get("type") == "field_truthy":
        return when.get("key", "?")
    op = when.get("op")
    if op:
        return f"{op}(...)"
    return "?"


def _serialize_definition(defn: WorkflowDef) -> dict:
    """Serialize a WorkflowDef for the observer UI (Exp-D flowchart)."""
    node_id_list = defn.node_ids  # ordered list for resolving implicit targets
    nodes = []
    for idx, (nid, nd) in enumerate(defn.nodes.items()):
        entry = {
            "id": nid,
            "title": nd.title,
            "instruction": nd.instruction,
            "show_all_fields": nd.show_all_fields,
        }
        # Fields as array
        if nd.fields:
            entry["fields"] = [
                {"key": f.key, "label": f.label, "type": f.type,
                 "options": f.options}
                for f in nd.fields.values()
            ]
        # Proceed
        if nd.proceed:
            p = {"label": nd.proceed.label}
            if nd.proceed.gate:
                p["requires"] = [
                    c.get("key", "")
                    for c in nd.proceed.gate.get("conditions", [])
                    if c.get("type") == "field_truthy"
                ] if nd.proceed.gate.get("op") == "AND" else []
            # Resolve target: explicit if set, otherwise next sequential node
            target = nd.proceed.target
            if not target and idx + 1 < len(node_id_list):
                target = node_id_list[idx + 1]
            if target:
                p["target"] = target
            entry["proceed"] = p
        # Router
        if nd.router:
            entry["router"] = [
                {"target": r.target, "when": r.when}
                for r in nd.router
            ]
        # Fork
        if nd.fork:
            branches = {}
            for bid, bdef in nd.fork.branches.items():
                branches[bid] = {"label": bdef.label, "nodes": bdef.nodes}
            entry["fork"] = {
                "label": nd.fork.label,
                "merge": nd.fork.merge,
                "branches": branches,
            }
        # Navigation
        if nd.navigation:
            entry["navigation"] = [
                {"action": nav.action, "label": nav.label, "node": nav.node}
                for nav in nd.navigation
            ]
        # Actions
        if nd.actions:
            entry["actions"] = [
                {"action": a.action, "label": a.label}
                for a in nd.actions
            ]
        nodes.append(entry)
    return {
        "workflow_id": defn.workflow_id,
        "workflow_title": defn.workflow_title,
        "workflow_description": defn.workflow_description,
        "nodes": nodes,
    }


def render_page(defn: WorkflowDef, data: dict, workflow_id: str) -> dict:
    """Render the current workflow state as the page dict."""
    node_id = data.get("node", defn.node_ids[0] if defn.node_ids else "")
    node = defn.nodes.get(node_id)
    if not node:
        return {"error": f"Unknown node: {node_id}"}

    # Derive lifecycle banner — topology-aware
    lifecycle = _build_lifecycle(defn)
    lifecycle_current = node_id
    lifecycle_completed = data.get("completed_nodes", [])

    state = {
        "workflow": defn.workflow_title,
        "node": node_id,
        "node_title": node.title,
        "lifecycle": lifecycle,
        "lifecycle_current": lifecycle_current,
        "lifecycle_completed": lifecycle_completed,
        "completed_nodes": data.get("completed_nodes", []),
    }

    # Fork state — expose branch tracking for UI
    fork_state = data.get("fork_state")
    if fork_state:
        fork_node = defn.nodes.get(fork_state.get("fork_node"))
        fork_def = fork_node.fork if fork_node else None
        branch_display = {}
        for bid, bdata in fork_state.get("branches", {}).items():
            branch_label = bid
            if fork_def and bid in fork_def.branches:
                branch_label = fork_def.branches[bid].label
            branch_display[bid] = {
                "label": branch_label,
                "completed": bdata.get("completed", False),
                "current_node": bdata.get("node"),
            }
        state["fork_state"] = {
            "active_branch": fork_state.get("active_branch"),
            "branches": branch_display,
        }

    # Workflow definition for visual renderers (Exp-D flowchart)
    state["definition"] = _serialize_definition(defn)

    # Fields
    fields_display = _build_fields(defn, node, data)
    if fields_display:
        state["fields"] = fields_display

    # Lists
    for list_def in node.lists.values():
        items = data.get(list_def.key, [])
        state[list_def.key] = items

    # Table
    if _node_has_table(defn, node, data):
        table_data = data.get("table", {})
        cols = table_data.get("columns", [])
        rows = table_data.get("rows", [])
        ncols = len(cols)
        nrows = len(rows)
        state["table"] = {
            "columns": cols,
            "rows": rows,
            "properties": table_data.get("properties", data.get("properties", {})),
            "summary": f"{ncols} column{'s' if ncols != 1 else ''}, {nrows} row{'s' if nrows != 1 else ''}",
        }

    # Execution table
    if node.execution and data.get("execution"):
        engine = _load_engine(data)
        ps = engine.get_plan_state()
        state["execution_table"] = {
            "columns": ps.columns,
            "rows": [r.to_dict() for r in ps.rows],
        }

    # Affordances
    affordances = _build_affordances(defn, node, data, workflow_id)

    return {
        "state": state,
        "instructions": node.instruction,
        "affordances": affordances,
    }


def _build_fields(defn: WorkflowDef, node: NodeDef, data: dict) -> dict:
    """Build the fields display dict for the current node."""
    field_defs = defn.node_fields(node.id)
    if not field_defs:
        return {}

    fields = {}
    for fdef in field_defs.values():
        if not check_visibility(fdef.visible_when, data):
            continue

        ftype = fdef.type
        key = fdef.key
        label = fdef.label

        if ftype == "boolean":
            value = bool(data.get(key))
            instruction = fdef.instruction
        elif ftype == "computed":
            value = _evaluate_computed(defn, fdef, data)
            if value:
                instruction = fdef.instruction_when_true or fdef.instruction
            else:
                instruction = fdef.instruction_when_false or fdef.instruction
        else:
            value = trunc(data.get(key))
            instruction = fdef.instruction

        entry = make_field(value, instruction)

        # Expose options for select fields
        if ftype == "select":
            options = _resolve_options(defn, fdef, data)
            if options:
                entry["options"] = options

        fields[label] = entry

    return fields


def _evaluate_computed(defn: WorkflowDef, fdef: FieldDef, data: dict) -> bool:
    """Evaluate a computed field. Returns the computed boolean value."""
    compute = fdef.compute
    if not compute:
        return False

    if compute.get("type") == "set_membership":
        key = compute.get("key", "")
        set_ref = compute.get("set_ref", "")
        val = data.get(key)
        member_set = set(defn.option_sets.get(set_ref, []))
        return val in member_set

    return False


def _resolve_options(defn: WorkflowDef, fdef: FieldDef, data: dict) -> list[str]:
    """Resolve options for a select field, including dynamic options."""
    # Dynamic options take priority — options depend on another field's value
    if fdef.dynamic_options:
        source_key = fdef.dynamic_options.get("source_key", "")
        mapping = fdef.dynamic_options.get("mapping", {})
        source_val = data.get(source_key)
        if source_val and str(source_val) in mapping:
            return mapping[str(source_val)]
        return fdef.dynamic_options.get("default", [])

    if fdef.options:
        return fdef.options

    if fdef.options_from:
        raw_options = defn.option_sets.get(fdef.options_from, [])
        if fdef.annotate_from and fdef.annotation:
            annotate_set = set(defn.option_sets.get(fdef.annotate_from, []))
            return [
                f"{opt} {fdef.annotation}" if opt in annotate_set else opt
                for opt in raw_options
            ]
        return list(raw_options)

    return []


def _build_affordances(
    defn: WorkflowDef, node: NodeDef, data: dict, workflow_id: str
) -> list[dict]:
    """Generate all affordances for the current node."""
    affordances = []
    n = 1
    api = f"/agent/{workflow_id}"

    # 1. Field affordances
    field_defs = defn.node_fields(node.id)
    for fdef in field_defs.values():
        if not check_visibility(fdef.visible_when, data):
            continue

        ftype = fdef.type
        if ftype in ("text", "boolean", "select"):
            current = data.get(fdef.key)
            if ftype == "boolean":
                current = bool(current)

            if isinstance(current, str) and current:
                display = f'"{trunc(current, 50)}"'
            else:
                display = json.dumps(current)

            a = {
                "id": n,
                "label": f"Set {fdef.label} (current: {display})",
                "method": "POST",
                "url": f"{api}/{fdef.key}",
                "body": {"value": "<value>"},
            }
            if ftype == "boolean":
                a["parameters"] = {"value": {"options": [True, False]}}
            elif ftype == "select":
                options = _resolve_options(defn, fdef, data)
                if options:
                    a["parameters"] = {"value": {"options": options}}
            affordances.append(a)
            n += 1

    # 2. List affordances
    for list_def in node.lists.values():
        n = _build_list_affordances(list_def, data, api, affordances, n)

    # 3. Navigation affordances (with conditional gates)
    for nav in node.navigation:
        # Evaluate when condition if present
        if nav.when:
            passed, _ = evaluate(nav.when, data)
            if not passed:
                continue
        nav_body = {}
        if nav.node:
            nav_body["node"] = nav.node
        a = {
            "id": n,
            "label": nav.label,
            "method": "POST",
            "url": f"{api}/{nav.action}",
            "body": nav_body,
        }
        affordances.append(a)
        n += 1

    # 4a. Fork gate (mutually exclusive with proceed)
    if node.fork:
        gate = node.fork.gate
        if gate:
            passed, _ = evaluate(gate, data)
        else:
            passed = True
        if passed:
            a = {
                "id": n,
                "label": node.fork.label,
                "method": "POST",
                "url": f"{api}/proceed",
                "body": {},
            }
            affordances.append(a)
            n += 1

    # 4b. Proceed gate (with optional target) — skip if node has fork
    elif node.proceed:
        gate = node.proceed.gate
        if gate:
            passed, _ = evaluate(gate, data)
        else:
            passed = True
        if passed:
            body = {}
            if node.proceed.target:
                body["target"] = node.proceed.target
            a = {
                "id": n,
                "label": node.proceed.label,
                "method": "POST",
                "url": f"{api}/proceed",
                "body": body,
            }
            affordances.append(a)
            n += 1

    # 4c. Branch switch affordances (when inside a fork)
    fork_state = data.get("fork_state")
    if fork_state:
        fork_node = defn.nodes.get(fork_state.get("fork_node"))
        fork_def = fork_node.fork if fork_node else None
        active_bid = fork_state.get("active_branch")
        for bid, bdata in fork_state.get("branches", {}).items():
            if bid == active_bid or bdata.get("completed"):
                continue
            branch_label = bid
            if fork_def and bid in fork_def.branches:
                branch_label = fork_def.branches[bid].label
            a = {
                "id": n,
                "label": f"Switch to {branch_label}",
                "method": "POST",
                "url": f"{api}/switch_branch",
                "body": {"branch": bid},
            }
            affordances.append(a)
            n += 1

    # 5. Node actions
    for act in node.actions:
        a = {
            "id": n,
            "label": act.label,
            "method": "POST",
            "url": f"{api}/{act.action}",
            "body": {},
        }
        affordances.append(a)
        n += 1

    # 6. Table structural affordances
    if _node_has_table(defn, node, data) and not node.execution:
        n = _build_table_affordances(defn, node, data, api, affordances, n)

    # 7. Table execution affordances
    if node.execution and data.get("execution"):
        n = _build_execution_affordances(data, api, affordances, n)

        # Complete gate
        engine = _load_engine(data)
        if engine.get_plan_state().status == "completed":
            affordances.append({
                "id": n, "label": "Complete Execution",
                "method": "POST", "url": f"{api}/complete",
                "body": {},
            })
            n += 1

    return affordances


def _build_list_affordances(list_def, data, api, affordances, n):
    """Generate affordances for a list content primitive."""
    from .schema import ListDef
    items = data.get(list_def.key, [])
    ops = set(list_def.operations)

    # Add item
    if "add" in ops:
        body = {}
        params = {}
        for fkey, fld in list_def.item_schema.items():
            body[fkey] = f"<{fkey}>"
            p = {}
            if fld.options:
                p["options"] = fld.options
            params[fkey] = p
        affordances.append({
            "id": n, "label": f"Add {list_def.label} item",
            "method": "POST", "url": f"{api}/list_add",
            "body": {"list_key": list_def.key, **body},
            "parameters": params,
        })
        n += 1

    if items:
        indices = list(range(len(items)))
        # Build labels from first text field in schema, or index
        first_key = next(iter(list_def.item_schema), None)
        labels = [str(item.get(first_key, i)) if isinstance(item, dict) else str(i) for i, item in enumerate(items)]

        # Select (focus) item
        if list_def.focus:
            focused = data.get(f"_focused_{list_def.key}")
            focused_label = labels[focused] if focused is not None and focused < len(items) else None
            affordances.append({
                "id": n, "label": f"Select {list_def.label} item (focused: {json.dumps(focused_label)})",
                "method": "POST", "url": f"{api}/list_select",
                "body": {"list_key": list_def.key, "index": "<index>"},
                "parameters": {"index": {"options": indices, "labels": labels}},
            })
            n += 1

        # Edit item
        if "edit" in ops:
            params = {"index": {"options": indices, "labels": labels}}
            for fkey, fld in list_def.item_schema.items():
                p = {"description": f"New value (omit to keep current)"}
                if fld.options:
                    p["options"] = fld.options
                params[fkey] = p
            affordances.append({
                "id": n, "label": f"Edit {list_def.label} item",
                "method": "POST", "url": f"{api}/list_edit",
                "body": {"list_key": list_def.key, "index": "<index>"},
                "parameters": params,
            })
            n += 1

        # Remove item
        if "remove" in ops:
            affordances.append({
                "id": n, "label": f"Remove {list_def.label} item",
                "method": "POST", "url": f"{api}/list_remove",
                "body": {"list_key": list_def.key, "index": "<index>"},
                "parameters": {"index": {"options": indices, "labels": labels}},
            })
            n += 1

        # Reorder item
        if "reorder" in ops and len(items) > 1:
            affordances.append({
                "id": n, "label": f"Move {list_def.label} item up",
                "method": "POST", "url": f"{api}/list_reorder",
                "body": {"list_key": list_def.key, "index": "<index>", "direction": "up"},
                "parameters": {"index": {"options": indices, "labels": labels}},
            })
            n += 1

    return n


def _node_has_table(defn: WorkflowDef, node: NodeDef, data: dict) -> bool:
    """Check if a node should display/manage a table."""
    return node.table is not None or node.execution


def _load_engine(data: dict):
    """Hydrate a PlanEngine from table data + execution state."""
    table_data = data.get("table", {})
    columns = [ColumnDef.from_dict(c) for c in table_data.get("columns", [])]
    plan = PlanDefinition(
        cr_id="WF",
        columns=columns,
        rows=table_data.get("rows", []),
        table_properties={
            "sequentialExecution": table_data.get("properties", data.get("properties", {})).get("sequential_execution", False),
        },
    )
    exec_state = data.get("execution")
    if exec_state:
        state = ExecutionState.from_dict(exec_state)
    else:
        state = ExecutionState(cr_id="WF")
    return PlanEngine(plan, state)


def _build_table_affordances(defn, node, data, api, affordances, n):
    """Generate table structural affordances."""
    table_def = node.table
    if not table_def:
        return n
    ops = set(table_def.operations)
    table_data = data.get("table", {})
    cols = table_data.get("columns", [])
    rows = table_data.get("rows", [])
    col_indices = list(range(len(cols)))
    col_labels = [c["name"] for c in cols]

    if "add_column" in ops:
        a = {
            "id": n, "label": "Add column",
            "method": "POST", "url": f"{api}/add_column",
            "body": {"name": "<name>", "type": "<type>"},
            "parameters": {"name": {}, "type": {"options": list(defn.column_types.keys())}},
        }
        # Add type descriptions if available
        if defn.column_types:
            type_info = [
                {"value": t, "label": info.get("label", t),
                 "category": info.get("category", ""),
                 "description": info.get("description", "")}
                for t, info in defn.column_types.items()
            ]
            a["parameters"]["type"]["descriptions"] = type_info
        affordances.append(a)
        n += 1

    if "add_row" in ops and cols:
        affordances.append({
            "id": n, "label": "Add row",
            "method": "POST", "url": f"{api}/add_row",
            "body": {},
        })
        n += 1

    if cols:
        if "rename_column" in ops:
            affordances.append({
                "id": n, "label": "Rename column",
                "method": "POST", "url": f"{api}/rename_column",
                "body": {"col": "<col>", "name": "<name>"},
                "parameters": {"col": {"options": col_indices, "labels": col_labels}, "name": {}},
            })
            n += 1

        if "set_column_type" in ops:
            affordances.append({
                "id": n, "label": "Set column type",
                "method": "POST", "url": f"{api}/set_column_type",
                "body": {"col": "<col>", "type": "<type>"},
                "parameters": {"col": {"options": col_indices, "labels": col_labels},
                               "type": {"options": list(defn.column_types.keys())}},
            })
            n += 1

        if "remove_column" in ops:
            affordances.append({
                "id": n, "label": "Remove column",
                "method": "POST", "url": f"{api}/remove_column",
                "body": {"col": "<col>"},
                "parameters": {"col": {"options": col_indices, "labels": col_labels}},
            })
            n += 1

        # Choice-list column management
        if "set_choices" in ops:
            choice_cols = [(i, c) for i, c in enumerate(cols) if c["type"] == "ex-choice-list"]
            if choice_cols:
                affordances.append({
                    "id": n, "label": "Set choices for column",
                    "method": "POST", "url": f"{api}/set_choices",
                    "body": {"col": "<col>", "choices": "<choices>"},
                    "parameters": {
                        "col": {"options": [i for i, _ in choice_cols], "labels": [c["name"] for _, c in choice_cols]},
                        "choices": {"description": "Array of valid option strings"},
                    },
                })
                n += 1

        # Acceptance criteria rule management
        if "set_rule" in ops:
            ae_cols = [(i, c) for i, c in enumerate(cols) if c["type"] == "ae-acceptance-criteria"]
            if ae_cols:
                exec_col_info = [
                    {"index": i, "name": c["name"], "type": c["type"]}
                    for i, c in enumerate(cols)
                    if c["type"] in ("ex-free-text", "ex-choice-list", "ex-cross-reference", "ex-signature")
                ]
                affordances.append({
                    "id": n, "label": "Set acceptance rule for column",
                    "method": "POST", "url": f"{api}/set_rule",
                    "body": {"col": "<col>", "rule": "<rule>"},
                    "parameters": {
                        "col": {"options": [i for i, _ in ae_cols], "labels": [c["name"] for _, c in ae_cols]},
                        "rule": {
                            "description": "Boolean expression tree. Structure: {\"op\": \"AND\"|\"OR\", \"conditions\": [...]}.",
                            "executable_columns": exec_col_info,
                        },
                    },
                })
                n += 1

        # Prerequisite management
        if "set_prerequisites" in ops and rows:
            prereq_cols = [(i, c) for i, c in enumerate(cols) if c["type"] == "ne-prerequisite"]
            if prereq_cols:
                row_ids = [f"Row-{i+1}" for i in range(len(rows))]
                affordances.append({
                    "id": n, "label": "Set prerequisites for cell",
                    "method": "POST", "url": f"{api}/set_prerequisites",
                    "body": {"row": "<row>", "col": "<col>", "prerequisites": "<prerequisites>"},
                    "parameters": {
                        "row": {"options": list(range(len(rows))), "labels": row_ids},
                        "col": {"options": [i for i, _ in prereq_cols], "labels": [c["name"] for _, c in prereq_cols]},
                        "prerequisites": {"description": "Array of row indices that must pass acceptance before this row"},
                    },
                })
                n += 1

    # Cell editing
    if "set_cell" in ops and cols and rows:
        affordances.append({
            "id": n, "label": "Set cell",
            "method": "POST", "url": f"{api}/set_cell",
            "body": {"row": "<row>", "col": "<col>", "value": "<value>"},
            "parameters": {
                "row": {"options": list(range(len(rows)))},
                "col": {"options": col_indices, "labels": col_labels},
                "value": {},
            },
        })
        n += 1

    if "remove_row" in ops and rows:
        affordances.append({
            "id": n, "label": "Remove row",
            "method": "POST", "url": f"{api}/remove_row",
            "body": {"row": "<row>"},
            "parameters": {"row": {"options": list(range(len(rows)))}},
        })
        n += 1

    # Table properties
    if "set_property" in ops:
        seq = table_data.get("properties", data.get("properties", {})).get("sequential_execution", False)
        affordances.append({
            "id": n, "label": f"Set sequential execution (current: {json.dumps(seq)})",
            "method": "POST", "url": f"{api}/set_property",
            "body": {"key": "sequential_execution", "value": "<value>"},
            "parameters": {"value": {"options": [True, False]}},
        })
        n += 1

    return n


def _build_execution_affordances(data, api, affordances, n):
    """Generate cell-action affordances from the execution engine."""
    engine = _load_engine(data)
    ps = engine.get_plan_state()

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
        elif action == "amend":
            cell_body["value"] = "<value>"
            col_def = engine.plan.columns[col]
            if is_choice_list(col_def.type) and col_def.choices:
                params["value"] = {"options": col_def.choices}
            else:
                params["value"] = {}
            label = f"Amend {col_name} for {row_id}"
        elif action == "sign":
            label = f"Sign {col_name} for {row_id}"
        elif action == "re-sign":
            label = f"Re-sign {col_name} for {row_id}"
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

    return n
