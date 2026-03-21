"""State rendering — builds the page dict from workflow state.

Produces the {state, instructions, affordances} page dict that the
observer UI expects. Affordance generation is delegated to the
AffordanceSource protocol in affordances.py.
"""

from __future__ import annotations

from .schema import WorkflowDef, FieldDef, NodeDef
from .evaluator import check_visibility
from .affordances import get_node_affordances, _load_engine, _resolve_options
from .providers import registry as provider_registry, resolve_bindings, ProviderUnavailableError

from ..utils import trunc, field as make_field


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


def _gate_labels(gate: dict) -> list[str]:
    """Walk a gate expression tree and return human-readable labels for each leaf."""
    if not gate:
        return []
    op = gate.get("op")
    if op in ("AND", "OR"):
        labels = []
        for c in gate.get("conditions", []):
            labels.extend(_gate_labels(c))
        return labels
    if op == "NOT":
        inner = _gate_labels(gate.get("condition", {}))
        return [f"NOT {l}" for l in inner]
    # Leaf condition
    ctype = gate.get("type", "")
    key = gate.get("key", "")
    if ctype == "field_truthy":
        return [key]
    if ctype == "field_equals":
        return [f"{key} = {gate.get('value', '?')!r}"]
    if ctype == "field_not_null":
        return [f"{key} is set"]
    if ctype == "set_membership":
        return [f"{key} in {gate.get('set_ref', '?')}"]
    if ctype == "table_has_columns":
        return ["table has columns"]
    if ctype == "table_has_rows":
        return ["table has rows"]
    if ctype == "provider_state":
        pid = gate.get("provider", "?")
        inner = gate.get("condition", {})
        inner_type = inner.get("type", "?")
        inner_val = inner.get("value", "")
        return [f"{pid}: {inner_type} = {inner_val!r}"]
    return [ctype or "?"]


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
                p["requires"] = _gate_labels(nd.proceed.gate)
                gate_op = nd.proceed.gate.get("op")
                if gate_op and gate_op != "AND":
                    p["gate_op"] = gate_op
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


def _query_providers(defn: WorkflowDef, data: dict):
    """Query all workflow-level providers and cache results in data.

    Populates _provider_cache_{pid} and _provider_bindings_{pid} as
    transient keys. These are stripped before persistence by app.py.
    """
    for pid, pdef in defn.providers.items():
        provider = provider_registry.get(pid)
        if not provider:
            continue
        bindings = resolve_bindings(pdef.bindings, data)
        data[f"_provider_bindings_{pid}"] = bindings
        try:
            data[f"_provider_cache_{pid}"] = provider.query(bindings)
        except ProviderUnavailableError:
            data[f"_provider_cache_{pid}"] = None


def render_page(defn: WorkflowDef, data: dict, workflow_id: str,
                 instance_id: str | None = None) -> dict:
    """Render the current workflow state as the page dict."""
    node_id = data.get("node", defn.node_ids[0] if defn.node_ids else "")
    node = defn.nodes.get(node_id)
    if not node:
        return {"error": f"Unknown node: {node_id}"}

    # Query external providers (before rendering — keeps render pure)
    if defn.providers:
        _query_providers(defn, data)

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

    # Provider exposed fields — projected as read-only into fields_display
    provider_states = {}
    for pid, pnode_def in node.provider_nodes.items():
        cached = data.get(f"_provider_cache_{pid}")
        if cached is None:
            # Provider unavailable — show diagnostic field
            if pid in defn.providers:
                fields_display[f"{pid} (unavailable)"] = make_field(
                    "Cannot reach provider", "This provider is currently unavailable."
                )
            continue
        provider_states[pid] = cached
        for expose_def in pnode_def.expose:
            value = cached.get(expose_def.key)
            entry = make_field(value, expose_def.instruction)
            entry["readonly"] = True
            entry["provider"] = pid
            fields_display[expose_def.label] = entry

    if fields_display:
        state["fields"] = fields_display
    if provider_states:
        state["providers"] = provider_states

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

    # Affordances (delegated to AffordanceSource protocol)
    affordances = get_node_affordances(defn, node, data, workflow_id, instance_id)

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


def _node_has_table(defn: WorkflowDef, node: NodeDef, data: dict) -> bool:
    """Check if a node should display/manage a table."""
    return node.table is not None or node.execution
