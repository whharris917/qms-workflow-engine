"""Stateless CLI for the workflow engine.

REQ-WFE-026: Command-line entry point.

Each invocation is a single command. Session state (current graph, current node,
workspace) persists to .wfe/ between invocations. Every command prints the current
view with available actions - the agent never needs to ask for help.

Usage:
    wfe new <name>                              Create a new graph
    wfe load <path>                             Load a graph from YAML
    wfe view                                    Show current node
    wfe nodes                                   List all nodes
    wfe home                                    Jump to home node
    wfe go <node-id>                            Navigate to a connected node
    wfe add node [name]                         Create a new node
    wfe add field <node-id> <name> <type> [val] Add a field to a node
    wfe add edge <source> <target> [condition]  Create an edge
    wfe remove node <node-id>                   Delete a node
    wfe remove field <node-id> <name>           Remove a field
    wfe remove edge <source> <target>           Remove an edge
    wfe set <node-id> <field-name> <value>      Set or update a field value
    wfe fill <field-name> <value>               Fill a field on the current node
    wfe advance                                 Evaluate edges and move to next node
    wfe commit                                  Freeze graph structure
    wfe checkout                                Create draft copy for editing
    wfe save [path]                             Save graph to a specific path
    wfe template list                           List available templates
    wfe template show <id>                      Show a template definition
    wfe instantiate <template-id> [key=value]   Instantiate a template into current graph
    wfe db list                                 List all mock database keys
    wfe db get <key>                            Get a value from the mock database
    wfe db set <key> <value>                    Set a value in the mock database
    wfe workspace                               Show current workspace
    wfe workspace set <key> <value>             Set a workspace entry
    wfe workspace clear                         Clear all workspace entries
    wfe compile [path]                          Compile current graph to CR markdown
    wfe help                                    Show all commands
"""

from __future__ import annotations

import sys

from wfe.graph import CycleError, HomeNodeError, ImmutableGraphError
from wfe.render import HELP_TEXT, render_nodes, render_view
from wfe.session import NavigationError, NoSessionError, Session


def _load_builtin_hooks() -> None:
    """Load built-in hook implementations shipped with the engine."""
    from wfe import builtin_hooks  # noqa: F401 — registers hooks as side effect


def _load_local_hooks() -> None:
    """Auto-load workflow_hooks.py from CWD if present (like pytest's conftest.py).

    This registers domain-specific hook implementations without the engine
    needing to know anything about them. Local hooks may override builtins
    by re-registering the same name.
    """
    import importlib.util
    from pathlib import Path
    hook_file = Path("workflow_hooks.py")
    if hook_file.exists():
        spec = importlib.util.spec_from_file_location("workflow_hooks", hook_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)


def main(args: list[str] | None = None) -> None:
    _load_builtin_hooks()
    _load_local_hooks()
    args = args or sys.argv[1:]

    if not args:
        try:
            session = Session.resume()
            print(render_view(session.graph, session.current_node_id))
        except NoSessionError as e:
            print(str(e))
        return

    cmd = args[0].lower()

    try:
        if cmd == "new":
            _cmd_new(args[1:])
        elif cmd == "load":
            _cmd_load(args[1:])
        elif cmd == "view":
            _cmd_view()
        elif cmd == "nodes":
            _cmd_nodes()
        elif cmd == "home":
            _cmd_home()
        elif cmd == "go":
            _cmd_go(args[1:])
        elif cmd == "add":
            _cmd_add(args[1:])
        elif cmd == "remove":
            _cmd_remove(args[1:])
        elif cmd == "fill":
            _cmd_fill(args[1:])
        elif cmd == "advance":
            _cmd_advance()
        elif cmd == "commit":
            _cmd_commit()
        elif cmd == "checkout":
            _cmd_checkout()
        elif cmd == "save":
            _cmd_save(args[1:])
        elif cmd == "set":
            _cmd_set(args[1:])
        elif cmd == "draft":
            _cmd_draft(args[1:])
        elif cmd == "submit":
            _cmd_submit(args[1:])
        elif cmd == "template":
            _cmd_template(args[1:])
        elif cmd == "instantiate":
            _cmd_instantiate(args[1:])
        elif cmd == "db":
            _cmd_db(args[1:])
        elif cmd == "workspace":
            _cmd_workspace(args[1:])
        elif cmd == "compile":
            _cmd_compile(args[1:])
        elif cmd in ("help", "--help", "-h"):
            print(HELP_TEXT)
        else:
            print(f"Unknown command: {cmd}")
            print("Run 'wfe help' to see all commands.")
    except (
        ImmutableGraphError,
        CycleError,
        HomeNodeError,
        NavigationError,
        NoSessionError,
        KeyError,
        ValueError,
        FileNotFoundError,
    ) as e:
        print(f"Error: {e}")


def _cmd_new(args: list[str]) -> None:
    if not args:
        print("Usage: wfe new <name>")
        return
    name = args[0]
    session = Session.create(name)
    print(f"Created graph '{name}'.")
    print()
    print(render_view(session.graph, session.current_node_id))


def _cmd_load(args: list[str]) -> None:
    if not args:
        print("Usage: wfe load <name-or-path>")
        return
    from pathlib import Path
    path = args[0]
    # Resolve bare name: workflows/ takes priority over .wfe/ (which is session state)
    if not Path(path).exists():
        for candidate in [
            Path("workflows") / f"{path}.yaml",
            Path(".wfe") / f"{path}.yaml",
        ]:
            if candidate.exists():
                path = str(candidate)
                break
    from wfe.session import _get_session_id
    session = Session.load_from(path)
    sid = _get_session_id()
    session_note = f" [session: {sid}]" if sid != "default" else ""
    print(f"Loaded graph '{session.graph.name}'.{session_note}")
    print()
    print(render_view(session.graph, session.current_node_id))


def _cmd_view() -> None:
    session = Session.resume()
    print(render_view(session.graph, session.current_node_id))


def _cmd_nodes() -> None:
    session = Session.resume()
    print(render_nodes(session.graph, session.current_node_id))


def _cmd_home() -> None:
    session = Session.resume()
    session.home()
    session.persist()
    print(render_view(session.graph, session.current_node_id))


def _cmd_go(args: list[str]) -> None:
    if not args:
        print("Usage: wfe go <node-id>")
        return
    session = Session.resume()
    session.go(args[0])
    session.persist()
    print(render_view(session.graph, session.current_node_id))


def _cmd_add(args: list[str]) -> None:
    if not args:
        print("Usage: wfe add node|field|edge ...")
        return
    session = Session.resume()
    subcmd = args[0].lower()

    if subcmd == "node":
        name = args[1] if len(args) > 1 else None
        node = session.graph.add_node(name)
        session.persist()
        print(f"Created node: {node.id}")
        print()
        print(render_view(session.graph, session.current_node_id))

    elif subcmd == "field":
        if len(args) < 4:
            print("Usage: wfe add field <node-id> <name> <type> [value]")
            return
        node_id, name, type_ = args[1], args[2], args[3]
        value = " ".join(args[4:]) if len(args) > 4 else None
        session.graph.add_field(node_id, name, type_, value)
        session.persist()
        print(f"Added field '{name}' to {node_id}.")
        print()
        print(render_view(session.graph, session.current_node_id))

    elif subcmd == "edge":
        if len(args) < 3:
            print("Usage: wfe add edge <source> <target> [condition]")
            return
        source, target = args[1], args[2]
        condition = " ".join(args[3:]) if len(args) > 3 else None
        session.graph.add_edge(source, target, condition)
        session.persist()
        print(f"Created edge: {source} -> {target}")
        print()
        print(render_view(session.graph, session.current_node_id))

    else:
        print(f"Unknown: add {subcmd}. Use: add node | add field | add edge")


def _cmd_remove(args: list[str]) -> None:
    if not args:
        print("Usage: wfe remove node|field|edge ...")
        return
    session = Session.resume()
    subcmd = args[0].lower()

    if subcmd == "node":
        if len(args) < 2:
            print("Usage: wfe remove node <node-id>")
            return
        node_id = args[1]
        session.graph.remove_node(node_id)
        if session.current_node_id == node_id:
            session.current_node_id = session.graph.home_id
        session.persist()
        print(f"Removed node: {node_id}")
        print()
        print(render_view(session.graph, session.current_node_id))

    elif subcmd == "field":
        if len(args) < 3:
            print("Usage: wfe remove field <node-id> <name>")
            return
        session.graph.remove_field(args[1], args[2])
        session.persist()
        print(f"Removed field '{args[2]}' from {args[1]}.")
        print()
        print(render_view(session.graph, session.current_node_id))

    elif subcmd == "edge":
        if len(args) < 3:
            print("Usage: wfe remove edge <source> <target>")
            return
        session.graph.remove_edge(args[1], args[2])
        session.persist()
        print(f"Removed edge: {args[1]} -> {args[2]}")
        print()
        print(render_view(session.graph, session.current_node_id))

    else:
        print(f"Unknown: remove {subcmd}. Use: remove node | remove field | remove edge")


def _cmd_set(args: list[str]) -> None:
    if len(args) < 3:
        print("Usage: wfe set <node-id> <field-name> <value>")
        return
    session = Session.resume()
    node_id, field_name = args[0], args[1]
    value = " ".join(args[2:])
    node = session.graph._get_node(node_id)
    if field_name not in node.fields:
        raise KeyError(f"Field '{field_name}' not found on node '{node_id}'.")
    if not node.fields[field_name].writable:
        raise ValueError(f"Field '{field_name}' is read-only.")
    node.fields[field_name].value = value
    session.persist()
    print(f"Set {node_id}.{field_name} = {value!r}")
    print()
    print(render_view(session.graph, session.current_node_id))


def _cmd_fill(args: list[str]) -> None:
    if len(args) < 2:
        print("Usage: wfe fill <field-name> <value>")
        return
    session = Session.resume()
    field_name = args[0]
    value = " ".join(args[1:])
    session.fill(field_name, value)
    session.persist()
    print(f"Filled {session.current_node_id}.{field_name} = {value!r}")
    print()
    print(render_view(session.graph, session.current_node_id))


def _cmd_advance() -> None:
    session = Session.resume()
    target = session.advance()
    session.persist()
    print(f"Advanced to {target}.")
    print()
    print(render_view(session.graph, session.current_node_id))


def _cmd_commit() -> None:
    session = Session.resume()
    session.graph.commit()
    session.persist()
    print("Graph committed. Structure is now frozen.")
    print()
    print(render_view(session.graph, session.current_node_id))


def _cmd_checkout() -> None:
    session = Session.resume()
    session.graph = session.graph.checkout()
    session.current_node_id = session.graph.home_id
    session.persist()
    print("Checked out draft copy.")
    print()
    print(render_view(session.graph, session.current_node_id))


def _cmd_save(args: list[str]) -> None:
    session = Session.resume()
    if args:
        from pathlib import Path
        from wfe.persistence import save
        path = Path(args[0])
        save(session.graph, path)
        print(f"Saved to {path}")
    else:
        session.persist()
        print(f"Saved to {session.graph_path}")


def _cmd_draft(args: list[str]) -> None:
    from pathlib import Path
    from wfe.form import form_file, write_form
    session = Session.resume()
    path = Path(args[0]) if args else form_file()
    write_form(session.current_node, session.graph.name, path, session.templates)
    print(f"Form written to: {path}")
    print(f"Edit the file, then run: wfe submit")


def _cmd_submit(args: list[str]) -> None:
    from pathlib import Path
    from wfe.form import form_file, read_and_validate
    session = Session.resume()
    path = Path(args[0]) if args else form_file()
    values, errors = read_and_validate(path, session.current_node, session.templates)
    if errors:
        print("Form validation failed:")
        for e in errors:
            print(e)
        return
    for fname, val in values.items():
        session.graph.fill_field(session.current_node_id, fname, val)
    session.persist()
    print(f"Submitted {len(values)} field(s) from {path}.")
    print()
    print(render_view(session.graph, session.current_node_id))


def _cmd_template(args: list[str]) -> None:
    from wfe.template import TemplateLibrary
    lib = TemplateLibrary()

    if not args or args[0] == "list":
        ids = lib.list_ids()
        if not ids:
            print("No templates found in templates/")
            return
        print("Templates:")
        for tid in ids:
            print(f"  {tid}")
        return

    if args[0] == "show":
        if len(args) < 2:
            print("Usage: wfe template show <id>")
            return
        tmpl = lib.get(args[1])
        print(f"Template: {tmpl.id}")
        if tmpl.prompt:
            print(f"Prompt: {tmpl.prompt}")
        if tmpl.enter_hooks:
            print(f"Enter hooks: {tmpl.enter_hooks}")
        if tmpl.exit_hooks:
            print(f"Exit hooks: {tmpl.exit_hooks}")
        print("Fields:")
        for spec in tmpl.field_specs:
            kind = "parameter" if spec.parameter else ("default=" + repr(spec.default) if spec.default is not None else "writable" if spec.writable else "read-only")
            print(f"  {spec.name} [{spec.type}] ({kind})")
        print("Edges:")
        for et in tmpl.edge_templates:
            cond = f"  when: {et.condition}" if et.condition else ""
            print(f"  -> {et.to}{cond}")
        return

    print(f"Unknown: template {args[0]}. Use: template list | template show <id>")


def _cmd_instantiate(args: list[str]) -> None:
    if not args:
        print("Usage: wfe instantiate <template-id> [key=value ...]")
        return
    session = Session.resume()
    template_id = args[0]

    params = {}
    for kv in args[1:]:
        if "=" not in kv:
            print(f"Invalid parameter: {kv!r}. Expected key=value.")
            return
        k, v = kv.split("=", 1)
        params[k.strip()] = v.strip()

    from wfe.template import TemplateLibrary, instantiate
    lib = TemplateLibrary()
    tmpl = lib.get(template_id)
    node = instantiate(tmpl, session.graph, params=params)
    session.persist()
    print(f"Instantiated template '{template_id}' as node: {node.id}")
    print()
    print(render_view(session.graph, session.current_node_id))


def _cmd_db(args: list[str]) -> None:
    from wfe.database import MockDatabase
    db = MockDatabase()

    if not args or args[0] == "list":
        keys = db.list_keys()
        if not keys:
            print("Database is empty.")
            return
        for k in keys:
            print(f"  {k}: {db.get(k)!r}")
        return

    if args[0] == "get":
        if len(args) < 2:
            print("Usage: wfe db get <key>")
            return
        val = db.get(args[1])
        print(f"{args[1]}: {val!r}")
        return

    if args[0] == "set":
        if len(args) < 3:
            print("Usage: wfe db set <key> <value>")
            return
        key = args[1]
        value = " ".join(args[2:])
        db.set(key, value)
        print(f"Set {key} = {value!r}")
        return

    print(f"Unknown: db {args[0]}. Use: db list | db get <key> | db set <key> <value>")


def _cmd_workspace(args: list[str]) -> None:
    session = Session.resume()

    if not args:
        if not session.workspace:
            print("Workspace is empty.")
        else:
            for k, v in session.workspace.items():
                print(f"  {k}: {v!r}")
        return

    if args[0] == "set":
        if len(args) < 3:
            print("Usage: wfe workspace set <key> <value>")
            return
        key = args[1]
        value = " ".join(args[2:])
        session.workspace[key] = value
        session.persist()
        print(f"Workspace: {key} = {value!r}")
        return

    if args[0] == "clear":
        session.workspace.clear()
        session.persist()
        print("Workspace cleared.")
        return

    print(f"Unknown: workspace {args[0]}. Use: workspace | workspace set <key> <val> | workspace clear")


def _cmd_compile(args: list[str]) -> None:
    from pathlib import Path
    from wfe.compile import compile_graph
    session = Session.resume()
    output = compile_graph(session.graph)
    if args:
        out_path = Path(args[0])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Compiled to {out_path}")
    else:
        print(output)


if __name__ == "__main__":
    main()
