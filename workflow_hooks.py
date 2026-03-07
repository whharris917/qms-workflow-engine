"""Hook implementations for the workflow engine.

Auto-loaded by the CLI on startup if present in the working directory.
The engine has no knowledge of what any hook does — it only dispatches by name.

Hook names referenced in workflow YAML must be registered here (or in another
file that is loaded before the workflow executes).
"""

from __future__ import annotations

from wfe.hooks import HookContext, HookResult, register


def _fv(node, field_name: str) -> str | None:
    """Read a field's string value, or None if absent/empty."""
    f = node.fields.get(field_name)
    return str(f.value) if f and f.value is not None else None


def _to_bool(val, default: bool) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "yes", "1")
    return default


def _parse_hook_list(val) -> list[str]:
    if isinstance(val, list):
        return [str(h).strip() for h in val if str(h).strip()]
    if val:
        return [h.strip() for h in str(val).splitlines() if h.strip()]
    return []


@register("init_target_graph")
def init_target_graph(ctx: HookContext) -> HookResult:
    """Create a new empty graph named after the 'workflow_name' field.

    Reads:  ctx.current_node.fields['workflow_name']
    Writes: ctx.workspace['target_path'], ctx.workspace['target_name']
    """
    name = _fv(ctx.current_node, "workflow_name")
    if not name or not name.strip():
        return HookResult(False, "Fill 'workflow_name' before advancing.")

    from pathlib import Path
    from wfe.graph import Graph
    from wfe.persistence import save

    name = name.strip()
    target = Graph(name=name)
    session_dir = Path(ctx.workspace.get("_session_dir", ".wfe/sessions/default"))
    session_dir.mkdir(parents=True, exist_ok=True)
    target_path = session_dir / f"target_{name}.yaml"
    save(target, target_path)

    ctx.workspace["target_path"] = str(target_path)
    ctx.workspace["target_name"] = name
    print(f"Initialized target graph '{name}' at {target_path}")
    return HookResult(True)


@register("build_node_chain")
def build_node_chain(ctx: HookContext) -> HookResult:
    """Build a workflow graph from a list of node definitions.

    Reads from node fields:
      nodes   list of dicts; each entry is either template-based or inline.

    Template-based (node structure comes from a pre-existing template):
      - template: ei
        task_description: Do the thing
        vr_required: false

    Inline (node structure defined directly in the entry):
      - id: define          # optional logical name; used as ID prefix and for edge references
        prompt: "..."
        fields:             # list of field specs: {name, type, value, writable, parameter}
          - name: my_field
            type: string
        exit_hooks:         # list of hook names
          - my_hook
        edges:              # optional; if absent, auto-wire to next node in list
          - target: done    # references another node's logical 'id'
            condition: ""   # optional

    Nodes are wired in order by default (node_i -> node_i+1). The first node
    becomes the home of the target graph. The last node is a terminal unless
    it has explicit edges.
    """
    node = ctx.current_node
    nodes_field = node.fields.get("nodes")
    raw_nodes = nodes_field.value if nodes_field else None

    if not raw_nodes:
        return HookResult(False, "Fill 'nodes' before advancing.")

    target_path_str = ctx.workspace.get("target_path")
    if not target_path_str:
        return HookResult(False, "No target graph. Was init_target_graph run?")

    from pathlib import Path
    from wfe.persistence import load, save
    from wfe.template import instantiate

    target_path = Path(target_path_str)
    if not target_path.exists():
        return HookResult(False, f"Target graph not found: {target_path}")

    target = load(target_path)

    def _next_cond(tmpl):
        for et in tmpl.edge_templates:
            if et.to == "{next}":
                return et.condition
        return None

    # --- Pass 1: create all nodes ---
    created = []  # list of {entry, node, logical_id, template}
    id_map = {}   # logical_id -> actual node id

    for i, raw_entry in enumerate(raw_nodes, start=1):
        if not isinstance(raw_entry, dict):
            return HookResult(False, f"'nodes' entry {i}: expected a dict, got {type(raw_entry).__name__}.")
        entry = dict(raw_entry)

        if "template" in entry:
            tmpl_id = str(entry["template"])
            if ctx.templates is None:
                return HookResult(False, "TemplateLibrary not available.")
            try:
                tmpl = ctx.templates.get(tmpl_id)
            except KeyError:
                available = ", ".join(ctx.templates.list_ids()) or "(none)"
                return HookResult(False, f"'nodes' entry {i}: template {tmpl_id!r} not found. Available: {available}")
            reserved = {"template", "id", "edges"}
            params = {k: v for k, v in entry.items() if k not in reserved}
            expected = {s.name for s in tmpl.field_specs if s.parameter}
            missing = expected - set(params.keys())
            if missing:
                return HookResult(False, f"'nodes' entry {i} (template={tmpl_id!r}): missing field(s): {', '.join(sorted(missing))}.")
            logical_id = entry.get("id") or tmpl_id
            created_node = instantiate(tmpl, target, params=params, name_prefix=logical_id)
            created.append({"entry": entry, "node": created_node, "logical_id": logical_id, "template": tmpl})

        else:
            logical_id = str(entry.get("id", f"node-{i}"))
            created_node = target.add_node(logical_id)
            if entry.get("label"):
                created_node.label = str(entry["label"])
            if entry.get("prompt"):
                created_node.prompt = str(entry["prompt"])
            created_node.enter_hooks = _parse_hook_list(entry.get("enter_hooks", []))
            created_node.exit_hooks = _parse_hook_list(entry.get("exit_hooks", []))
            for fi, fspec in enumerate(entry.get("fields") or [], start=1):
                if not isinstance(fspec, dict):
                    return HookResult(False, f"'nodes' entry {i}, field {fi}: expected a dict.")
                fname = str(fspec.get("name", "")).strip()
                ftype = str(fspec.get("type", "string")).strip()
                if not fname:
                    return HookResult(False, f"'nodes' entry {i}, field {fi}: missing 'name'.")
                target.add_field(
                    created_node.id, fname, ftype,
                    value=fspec.get("value", None),
                    writable=_to_bool(fspec.get("writable", True), True),
                    parameter=_to_bool(fspec.get("parameter", False), False),
                )
            created.append({"entry": entry, "node": created_node, "logical_id": logical_id, "template": None})

        id_map[logical_id] = created_node.id

    if not created:
        return HookResult(False, "'nodes' is empty.")

    # First node becomes home (discards the bare placeholder home from Graph.__init__)
    target.set_home(created[0]["node"].id)

    # --- Pass 2: wire edges ---
    for i, item in enumerate(created):
        n = item["node"]
        tmpl = item["template"]
        explicit_edges = item["entry"].get("edges")  # None=absent, []=explicit terminal

        if explicit_edges is not None:
            for ej, edge_spec in enumerate(explicit_edges, start=1):
                if not isinstance(edge_spec, dict):
                    return HookResult(False, f"'nodes' entry {i + 1}, edge {ej}: expected a dict.")
                raw_target = str(edge_spec.get("target", "")).strip()
                if not raw_target:
                    return HookResult(False, f"'nodes' entry {i + 1}, edge {ej}: missing 'target'.")
                actual_target = id_map.get(raw_target, raw_target)
                if actual_target not in target.nodes:
                    return HookResult(False, f"'nodes' entry {i + 1}, edge {ej}: target {raw_target!r} not found.")
                target.add_edge(n.id, actual_target, edge_spec.get("condition") or None)
        elif i + 1 < len(created):
            target.add_edge(n.id, created[i + 1]["node"].id, _next_cond(tmpl) if tmpl else None)

    save(target, target_path)
    ctx.workspace["chain_length"] = len(created)
    tmpl_names = list(dict.fromkeys(c["template"].id for c in created if c["template"]))
    inline_count = sum(1 for c in created if not c["template"])
    parts = []
    if tmpl_names:
        parts.append(f"{len(created) - inline_count} template node(s): {', '.join(tmpl_names)}")
    if inline_count:
        parts.append(f"{inline_count} inline node(s)")
    print(f"Built: {', '.join(parts)}.")
    return HookResult(True)


@register("save_workflow")
def save_workflow(ctx: HookContext) -> HookResult:
    """Commit the target graph and save it to workflows/.

    Reads: ctx.workspace['target_path'], ctx.workspace['target_name']
    """
    target_path_str = ctx.workspace.get("target_path")
    target_name = ctx.workspace.get("target_name")
    if not target_path_str or not target_name:
        return HookResult(False, "No target graph. Was init_target_graph run?")

    from pathlib import Path
    from wfe.persistence import load, save

    target_path = Path(target_path_str)
    if not target_path.exists():
        return HookResult(False, f"Target graph not found: {target_path}")

    target = load(target_path)
    target.commit()

    out_dir = Path("workflows")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{target_name}.yaml"
    save(target, out_path)

    ctx.workspace["saved_path"] = str(out_path)
    print(f"Workflow saved to {out_path}")
    return HookResult(True)


@register("save_template")
def save_template(ctx: HookContext) -> HookResult:
    """Write a template YAML file from node fields.

    Reads from node fields:
      template_id     - unique identifier
      prompt          - optional prompt text
      fields          - nodelist of field definitions
                        (each needs: name, type; optional: parameter, writable, default)
      edge_templates  - nodelist of edge definitions
                        (each needs: to; optional: condition)
      enter_hooks     - optional text list of hook names (one per line)
      exit_hooks      - optional text list of hook names (one per line)
    """
    node = ctx.current_node
    template_id = _fv(node, "template_id")
    if not template_id or not template_id.strip():
        return HookResult(False, "Fill 'template_id' before advancing.")

    import yaml
    from pathlib import Path

    def _parse_hooks(field_name):
        f = node.fields.get(field_name)
        if not f or not f.value:
            return []
        raw = f.value
        if isinstance(raw, list):
            return [str(h).strip() for h in raw if str(h).strip()]
        return [h.strip() for h in str(raw).splitlines() if h.strip()]

    tmpl_data = {"id": template_id.strip()}

    prompt = _fv(node, "prompt")
    if prompt:
        tmpl_data["prompt"] = prompt

    # Field definitions
    fields_field = node.fields.get("fields")
    raw_fields = fields_field.value if fields_field else None
    if raw_fields:
        field_list = []
        for i, entry in enumerate(raw_fields, start=1):
            if not isinstance(entry, dict):
                return HookResult(False, f"'fields' entry {i}: expected a dict.")
            name = entry.get("name", "").strip()
            ftype = entry.get("type", "").strip()
            if not name:
                return HookResult(False, f"'fields' entry {i}: missing 'name'.")
            if not ftype:
                return HookResult(False, f"'fields' entry {i}: missing 'type'.")
            fd = {"name": name, "type": ftype}
            if "parameter" in entry:
                fd["parameter"] = _to_bool(entry["parameter"], False)
            if "writable" in entry:
                fd["writable"] = _to_bool(entry["writable"], True)
            if "default" in entry and entry["default"] not in (None, ""):
                fd["default"] = entry["default"]
            field_list.append(fd)
        if field_list:
            tmpl_data["fields"] = field_list

    # Edge definitions
    edges_field = node.fields.get("edge_templates")
    raw_edges = edges_field.value if edges_field else None
    if raw_edges:
        edge_list = []
        for i, entry in enumerate(raw_edges, start=1):
            if not isinstance(entry, dict):
                return HookResult(False, f"'edge_templates' entry {i}: expected a dict.")
            to = entry.get("to", "").strip()
            if not to:
                return HookResult(False, f"'edge_templates' entry {i}: missing 'to'.")
            ed = {"to": to}
            cond = entry.get("condition", "")
            if cond:
                ed["condition"] = str(cond).strip()
            edge_list.append(ed)
        if edge_list:
            tmpl_data["edge_templates"] = edge_list

    enter_hooks = _parse_hooks("enter_hooks")
    if enter_hooks:
        tmpl_data["enter_hooks"] = enter_hooks

    exit_hooks = _parse_hooks("exit_hooks")
    if exit_hooks:
        tmpl_data["exit_hooks"] = exit_hooks

    out_dir = Path("templates")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{template_id.strip()}.yaml"
    with open(out_path, "w") as f:
        yaml.dump(tmpl_data, f, default_flow_style=False, sort_keys=False)

    print(f"Template saved to {out_path}")
    return HookResult(True)


@register("compile_cr")
def compile_cr(ctx: HookContext) -> HookResult:
    """Compile the current graph to a QMS CR markdown document.

    Reads:  ctx.workspace['cr_output_path']  (explicit path)
            ctx.workspace['cr_id']            (derives path: QMS/CR/{cr_id}/{cr_id}.md)
    Falls back to: QMS/CR/{graph.name}/{graph.name}.md
    """
    from pathlib import Path
    from wfe.compile import compile_graph

    output_path = ctx.workspace.get("cr_output_path")
    if not output_path:
        cr_id = ctx.workspace.get("cr_id") or ctx.graph.name
        output_path = f"QMS/CR/{cr_id}/{cr_id}.md"

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = compile_graph(ctx.graph)
    path.write_text(content, encoding="utf-8")
    print(f"Compiled CR to {path}")
    return HookResult(True)


@register("check_document_approved")
def check_document_approved(ctx: HookContext) -> HookResult:
    """Check that a document in the mock database is in APPROVED state.

    Reads: ctx.current_node.fields['doc_id']
    Queries: ctx.db
    """
    if ctx.db is None:
        return HookResult(False, "MockDatabase not available.")

    doc_id = _fv(ctx.current_node, "doc_id")
    if not doc_id:
        return HookResult(False, "No 'doc_id' field on current node.")

    state = ctx.db.get(f"{doc_id}.state")
    if state != "APPROVED":
        return HookResult(
            False,
            f"Document {doc_id} is not APPROVED (current state: {state!r})."
        )
    return HookResult(True)
