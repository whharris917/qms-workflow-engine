"""State rendering — builds the page dict from workflow state.

Produces the {state, instructions, affordances} page dict that the
observer UI expects. Affordance generation is delegated to the
AffordanceSource protocol in affordances.py.
"""

from __future__ import annotations

from .schema import WorkflowDef, FieldDef, NodeDef
from .evaluator import check_visibility, evaluate
from .affordances import get_node_affordances, _load_engine, _resolve_options
from .providers import registry as provider_registry, resolve_bindings, ProviderUnavailableError

from ..utils import trunc, field as make_field



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


def _serialize_definition_topology(defn: WorkflowDef) -> dict:
    """Serialize topology for the schematic banner.

    Includes only what definitionToSpine() needs: node id/title,
    proceed targets, router routes, and fork branches. Omits fields,
    instructions, navigation, actions, and proceed gate details.
    """
    node_id_list = defn.node_ids
    nodes = []
    for idx, (nid, nd) in enumerate(defn.nodes.items()):
        entry = {"id": nid, "title": nd.title}
        if nd.proceed:
            target = nd.proceed.target
            if not target and idx + 1 < len(node_id_list):
                target = node_id_list[idx + 1]
            if target:
                entry["proceed"] = {"target": target}
        if nd.router:
            entry["router"] = [
                {"target": r.target, "when": r.when}
                for r in nd.router
            ]
        if nd.fork:
            branches = {}
            for bid, bdef in nd.fork.branches.items():
                branches[bid] = {"label": bdef.label, "nodes": bdef.nodes}
            entry["fork"] = {
                "label": nd.fork.label,
                "merge": nd.fork.merge,
                "branches": branches,
            }
        nodes.append(entry)
    return {
        "workflow_id": defn.workflow_id,
        "workflow_title": defn.workflow_title,
        "nodes": nodes,
    }


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

    state = {
        "workflow": defn.workflow_title,
        "node": node_id,
        "node_title": node.title,
        "completed_nodes": data.get("completed_nodes", []),
        "definition": _serialize_definition_topology(defn),
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

    # Fields (with inline affordances)
    fields_display = _build_fields(defn, node, data)

    # Provider exposed fields — projected as read-only into fields_display
    provider_states = {}
    for pid, pnode_def in node.provider_nodes.items():
        cached = data.get(f"_provider_cache_{pid}")
        if cached is None:
            # Provider unavailable — show diagnostic field
            if pid in defn.providers:
                diag = make_field(
                    "Cannot reach provider", "This provider is currently unavailable."
                )
                diag["affordance"] = None
                fields_display[f"{pid} (unavailable)"] = diag
            continue
        provider_states[pid] = cached
        for expose_def in pnode_def.expose:
            value = cached.get(expose_def.key)
            entry = make_field(value, expose_def.instruction)
            entry["key"] = expose_def.key
            entry["readonly"] = True
            entry["provider"] = pid
            entry["affordance"] = None
            fields_display[expose_def.label] = entry

    # Build content: a single ordered list of elements in YAML definition order.
    # Groups are inserted at the position of their first visible member.
    field_to_gdef: dict[str, "FieldGroupDef"] = {}
    for gdef in node.field_groups.values():
        for fkey in gdef.fields:
            field_to_gdef[fkey] = gdef

    content_items: list[dict] = []
    seen_groups: set[str] = set()
    for fkey, fdef in defn.node_fields(node.id).items():
        gdef = field_to_gdef.get(fkey)
        if gdef:
            if gdef.label not in seen_groups:
                group_fields = []
                for gfkey in gdef.fields:
                    for lbl, fobj in fields_display.items():
                        if fobj.get("key") == gfkey:
                            entry = dict(fobj)
                            entry["label"] = lbl
                            group_fields.append(entry)
                            break
                if group_fields:
                    content_items.append({
                        "type": "group",
                        "label": gdef.label,
                        "instruction": gdef.instruction,
                        "affordance": None,
                        "fields": group_fields,
                    })
                    seen_groups.add(gdef.label)
        else:
            fobj = fields_display.get(fdef.label)
            if fobj is not None:
                entry = dict(fobj)
                entry["label"] = fdef.label
                content_items.append(entry)  # type already set by _build_fields

    if content_items:
        state["content"] = content_items
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
    all_affordances = get_node_affordances(defn, node, data, workflow_id, instance_id)

    # Partition affordances by anchor.
    # FieldSource tags with _field_label, TableStructuralSource tags with
    # _table_anchor / _col_index.  Everything else stays top-level.
    remaining = []
    field_affs_by_label: dict[str, dict] = {}
    field_group_affs_by_label: dict[str, dict] = {}
    table_affs: list[dict] = []
    col_affs: dict[int, list[dict]] = {}
    props_affs: list[dict] = []
    for aff in all_affordances:
        fl = aff.pop("_field_label", None)
        fgl = aff.pop("_field_group_label", None)
        ta = aff.pop("_table_anchor", None)
        ci = aff.pop("_col_index", None)
        if fl is not None:
            field_affs_by_label[fl] = aff
        elif fgl is not None:
            field_group_affs_by_label[fgl] = aff
        elif ta == "table":
            table_affs.append(aff)
        elif ta == "column" and ci is not None:
            col_affs.setdefault(ci, []).append(aff)
        elif ta == "properties":
            props_affs.append(aff)
        else:
            remaining.append(aff)

    # ── Emit all affordances (no focus filtering) ──
    aff_id = 1
    output_affordances = []

    # Field and field_group affordances: embed on content items
    for item in state.get("content", []):
        if item["type"] == "field":
            fa = field_affs_by_label.get(item["label"])
            if fa is not None:
                fa["id"] = aff_id
                aff_id += 1
                item["affordance"] = fa
                output_affordances.append(fa)
        elif item["type"] == "group":
            ga = field_group_affs_by_label.get(item["label"])
            if ga is not None:
                ga["id"] = aff_id
                aff_id += 1
                item["affordance"] = ga
                output_affordances.append(ga)

    # Table affordances
    for a in table_affs:
        a["id"] = aff_id
        aff_id += 1
        output_affordances.append(a)

    # Properties affordances
    for a in props_affs:
        a["id"] = aff_id
        aff_id += 1
        output_affordances.append(a)

    # Column affordances
    for ci_key in sorted(col_affs.keys()):
        for a in col_affs[ci_key]:
            a["id"] = aff_id
            aff_id += 1
            output_affordances.append(a)

    # Remaining (flow control, navigation, cell actions, etc.)
    for aff in remaining:
        aff["id"] = aff_id
        aff_id += 1
        output_affordances.append(aff)

    # Enrich state.table with anchored affordances
    if "table" in state:
        state["table"]["affordances"] = table_affs
        if props_affs:
            props = state["table"].get("properties", {})
            props["affordances"] = props_affs

        for ci, col_obj in enumerate(state["table"].get("columns", [])):
            col_obj["affordances"] = col_affs.get(ci, [])

    return {
        "state": state,
        "instructions": node.instruction,
        "affordances": output_affordances,
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

        if ftype == "toggle":
            raw = data.get(key)
            value = None if raw is None else bool(raw)
            instruction = fdef.instruction
        elif ftype == "indicator":
            value = _evaluate_computed(defn, fdef, data)
            if value:
                instruction = fdef.instruction_when_true or fdef.instruction
            else:
                instruction = fdef.instruction_when_false or fdef.instruction
        else:
            value = trunc(data.get(key))
            instruction = fdef.instruction

        entry = make_field(value, instruction)
        entry["key"] = key
        entry["type"] = ftype

        # Expose options for choice elements
        if ftype == "choice":
            options = _resolve_options(defn, fdef, data)
            if options:
                entry["options"] = options

        # Affordance is attached later by render_page() from the partitioned
        # affordance list.  Initialize to None (computed/readonly default).
        entry["affordance"] = None

        fields[label] = entry

    return fields


def _evaluate_computed(defn: WorkflowDef, fdef: FieldDef, data: dict) -> bool:
    """Evaluate a computed field using the unified expression evaluator."""
    compute = fdef.compute
    if not compute:
        return False
    # Inject option sets so set_membership leaves can resolve references
    for name, values in defn.option_sets.items():
        data[f"__option_set_{name}"] = set(values)
    passed, _ = evaluate(compute, data)
    return passed


def _node_has_table(defn: WorkflowDef, node: NodeDef, data: dict) -> bool:
    """Check if a node should display/manage a table."""
    return node.table is not None or node.execution
