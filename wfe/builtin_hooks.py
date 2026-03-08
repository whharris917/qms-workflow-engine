"""Built-in hook implementations for the workflow engine.

These hooks are generic engine utilities that ship with the engine itself.
They are auto-loaded by the CLI before any project-level workflow_hooks.py.
Local workflow_hooks.py may override any of these by re-registering the same name.

Parameterized hooks use colon-separated parameters in YAML:
    exit_hooks:
      - validate_field_in_db:system:controlled_submodules
      - lookup_entity_props:system:submodule_properties
      - extend_chain:ei:additional_eis
"""

from __future__ import annotations

from wfe.hooks import HookContext, HookResult, register


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Workflow construction hooks
# ---------------------------------------------------------------------------

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
            if entry.get("scaffold"):
                created_node.scaffold = _to_bool(entry["scaffold"], False)
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
                    block=_to_bool(fspec.get("block", False), False),
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
                spawns = edge_spec.get("spawns_workflow") or None
                if actual_target not in target.nodes:
                    if spawns:
                        from wfe.graph import Edge as _Edge
                        n.edges.append(_Edge(
                            target=actual_target,
                            condition=edge_spec.get("condition") or None,
                            spawns_workflow=str(spawns),
                        ))
                        continue
                    return HookResult(False, f"'nodes' entry {i + 1}, edge {ej}: target {raw_target!r} not found.")
                e = target.add_edge(n.id, actual_target, edge_spec.get("condition") or None)
                if spawns:
                    e.spawns_workflow = str(spawns)
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


@register("compile_to_file")
def compile_to_file(ctx: HookContext) -> HookResult:
    """Compile the current graph to a markdown document.

    Reads:  ctx.workspace['output_path']  (explicit path)
    Falls back to: compiled/{graph.name}.md
    """
    from pathlib import Path
    from wfe.compile import compile_graph

    output_path = ctx.workspace.get("output_path") or f"compiled/{ctx.graph.name}.md"
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = compile_graph(ctx.graph)
    path.write_text(content, encoding="utf-8")
    print(f"Compiled to {path}")
    return HookResult(True)


# ---------------------------------------------------------------------------
# Data-driven domain hooks (parameterized)
# ---------------------------------------------------------------------------

@register("validate_field_in_db")
def validate_field_in_db(ctx: HookContext, field_name: str, db_collection: str) -> HookResult:
    """Block advance if the named field's value is not in db[db_collection] (list).

    Usage in YAML:
        exit_hooks:
          - validate_field_in_db:system:controlled_submodules
    """
    if ctx.db is None:
        return HookResult(False, "Database not available.")

    value = _fv(ctx.current_node, field_name)
    if not value or not value.strip():
        return HookResult(False, f"Fill '{field_name}' before advancing.")
    value = value.strip()

    collection = ctx.db.get(db_collection)
    if not isinstance(collection, list):
        return HookResult(False, f"Database collection '{db_collection}' is not a list.")

    if value not in collection:
        valid = ", ".join(str(v) for v in collection)
        return HookResult(False, f"'{value}' is not a valid {field_name}. Valid: {valid}")

    return HookResult(True)


@register("lookup_entity_props")
def lookup_entity_props(ctx: HookContext, field_name: str, db_collection: str) -> HookResult:
    """Write db[db_collection][field_value] properties into ctx.workspace.

    The collection must be a dict of entity_name -> {prop: val, ...}.
    All properties are written directly to the workspace.

    Usage in YAML:
        exit_hooks:
          - lookup_entity_props:system:submodule_properties
    """
    if ctx.db is None:
        return HookResult(False, "Database not available.")

    value = _fv(ctx.current_node, field_name)
    if not value or not value.strip():
        return HookResult(False, f"Fill '{field_name}' before advancing.")
    value = value.strip()

    collection = ctx.db.get(db_collection)
    if not isinstance(collection, dict):
        return HookResult(False, f"Database collection '{db_collection}' is not a dict.")

    if value not in collection:
        return HookResult(False, f"'{value}' not found in {db_collection}.")

    props = collection[value]
    if not isinstance(props, dict):
        return HookResult(False, f"Properties for '{value}' in {db_collection} are not a dict.")

    ctx.workspace.update(props)
    print(f"Loaded properties for '{value}': {props}")
    return HookResult(True)


@register("set_workspace")
def set_workspace(ctx: HookContext, key: str, value: str) -> HookResult:
    """Write a literal string value to ctx.workspace[key].

    Runs on all exits from the node (edge-agnostic). Useful for setting defaults
    that later hooks on other paths may overwrite. Last write wins.

    Usage in YAML:
        exit_hooks:
          - set_workspace:cr_type:cr-non-code
    """
    ctx.workspace[key] = value
    return HookResult(True)


@register("pull_from_workspace")
def pull_from_workspace(ctx: HookContext, key: str) -> HookResult:
    """Write ctx.workspace[key] into ctx.current_node.fields[key].

    The field must exist on the node. Bypasses the writable check — this is
    an engine operation, not user input.

    Usage in YAML:
        enter_hooks:
          - pull_from_workspace:cr_type
    """
    val = ctx.workspace.get(key)
    if val is None:
        return HookResult(False, f"Workspace key '{key}' not set.")

    if key not in ctx.current_node.fields:
        return HookResult(False, f"Field '{key}' not found on node '{ctx.current_node.id}'.")

    ctx.current_node.fields[key].value = val  # bypass writable check (engine operation)
    return HookResult(True)


@register("load_workflow")
def load_workflow(ctx: HookContext, workspace_key: str = "cr_type") -> HookResult:
    """Load a workflow template and save a DRAFT copy as a new instance.

    Reads:  ctx.workspace[workspace_key]  — template name (e.g. 'cr-sdlc')
    Writes: ctx.workspace['generated_cr_path']
            ctx.workspace['generated_cr_compiled']

    Usage in YAML:
        exit_hooks:
          - load_workflow              # uses default key 'cr_type'
          - load_workflow:my_key       # uses custom workspace key
    """
    import uuid
    from pathlib import Path
    from wfe.compile import compile_graph
    from wfe.persistence import load, save

    template_name = ctx.workspace.get(workspace_key)
    if not template_name:
        return HookResult(False, f"Workspace key '{workspace_key}' not set.")

    template_path = Path("workflows") / f"{template_name}.yaml"
    if not template_path.exists():
        return HookResult(False, f"Workflow template not found: {template_path}")

    graph = load(template_path)

    # Generate unique instance name
    instance_name = f"{template_name}-{uuid.uuid4().hex[:8]}"
    graph.name = instance_name

    out_dir = Path("workflows")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{instance_name}.yaml"
    save(graph, out_path)

    compiled_dir = Path("compiled")
    compiled_dir.mkdir(exist_ok=True)
    compiled_path = compiled_dir / f"{instance_name}.md"
    compiled_path.write_text(compile_graph(graph), encoding="utf-8")

    ctx.workspace["generated_cr_path"] = str(out_path)
    ctx.workspace["generated_cr_compiled"] = str(compiled_path)
    print(f"Created workflow instance: {out_path}")
    print(f"Compiled to: {compiled_path}")
    return HookResult(True)


@register("extend_chain")
def extend_chain(ctx: HookContext, template_id: str, items_field: str) -> HookResult:
    """Instantiate template for each line in current_node.fields[items_field].

    Appends new nodes before the terminal (no-edges) node in the current graph.
    Idempotent: skips items whose first parameter field value already exists on a node.

    Usage in YAML:
        exit_hooks:
          - extend_chain:ei:additional_eis
    """
    raw = _fv(ctx.current_node, items_field)
    if not raw:
        return HookResult(True)  # Nothing to do

    new_items = [line.strip() for line in raw.splitlines() if line.strip()]
    if not new_items:
        return HookResult(True)

    if ctx.templates is None:
        return HookResult(False, "TemplateLibrary not available.")

    try:
        tmpl = ctx.templates.get(template_id)
    except KeyError:
        return HookResult(False, f"Template '{template_id}' not found.")

    # Find the first parameter field — its name is used for idempotency checking
    param_specs = [spec for spec in tmpl.field_specs if spec.parameter]
    if not param_specs:
        return HookResult(False, f"Template '{template_id}' has no parameter fields.")
    param_name = param_specs[0].name

    # Find {next} condition from template edge templates
    next_cond: str | None = None
    for et in tmpl.edge_templates:
        if et.to == "{next}":
            next_cond = et.condition
            break

    g = ctx.graph

    # Find terminal node: the first node with no outgoing edges at all
    terminal_id: str | None = None
    for nid, node in g.nodes.items():
        if not node.edges:
            terminal_id = nid
            break
    if terminal_id is None:
        return HookResult(False, "No terminal node found in graph.")

    # Collect existing parameter values for idempotency
    existing_values: set[str] = set()
    for node in g.nodes.values():
        f = node.fields.get(param_name)
        if f and f.value is not None:
            existing_values.add(str(f.value))

    # Find the "last" node: the one with a navigation edge to terminal via next_cond
    last_id: str = terminal_id  # sentinel: will be updated below
    for nid, node in g.nodes.items():
        for edge in node.edges:
            if (
                edge.target == terminal_id
                and edge.condition == next_cond
                and edge.spawns_workflow is None
            ):
                last_id = nid
                break

    from wfe.template import instantiate

    for item in new_items:
        if item in existing_values:
            continue  # Idempotent: skip duplicates

        # Instantiate template; {next} resolves to terminal
        new_node = instantiate(
            tmpl, g,
            params={param_name: item},
            edge_map={"{next}": terminal_id},
            name_prefix=template_id,
        )

        # Rewire: remove last_id → terminal (next_cond), add last_id → new_node
        if last_id != terminal_id:
            last_node = g.nodes[last_id]
            last_node.edges = [
                e for e in last_node.edges
                if not (
                    e.target == terminal_id
                    and e.condition == next_cond
                    and e.spawns_workflow is None
                )
            ]
            g.add_edge(last_id, new_node.id, next_cond)

        last_id = new_node.id
        existing_values.add(item)
        print(f"Extended chain with: {item!r}")

    return HookResult(True)
