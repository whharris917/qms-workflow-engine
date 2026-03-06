"""Stateless CLI for the workflow engine.

REQ-WFE-026: Command-line entry point.

Each invocation is a single command. Session state (current graph, current node)
persists to .wfe/ between invocations. Every command prints the current view
with available actions - the agent never needs to ask for help.

Usage:
    wfe new <name>                              Create a new graph
    wfe load <path>                             Load a graph from YAML
    wfe view                                    Show current node
    wfe nodes                                   List all nodes
    wfe home                                    Jump to home node
    wfe go <node-id>                            Navigate to a connected node
    wfe add node [name]                         Create a new node
    wfe add slot <node-id> <name> <type> [val]  Add a slot to a node
    wfe add edge <source> <target> [condition]  Create an edge
    wfe remove node <node-id>                   Delete a node
    wfe remove slot <node-id> <name>            Remove a slot
    wfe remove edge <source> <target>           Remove an edge
    wfe commit                                  Freeze graph structure
    wfe checkout                                Create draft copy for editing
    wfe save [path]                             Save graph to a specific path
"""

from __future__ import annotations

import sys

from wfe.graph import CycleError, HomeNodeError, ImmutableGraphError
from wfe.render import render_nodes, render_view
from wfe.session import NavigationError, NoSessionError, Session


def main(args: list[str] | None = None) -> None:
    args = args or sys.argv[1:]

    if not args:
        # No command - show current view or guide to create
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
        elif cmd == "commit":
            _cmd_commit()
        elif cmd == "checkout":
            _cmd_checkout()
        elif cmd == "save":
            _cmd_save(args[1:])
        else:
            print(f"Unknown command: {cmd}")
            print("Use 'wfe new <name>' to create a graph, or 'wfe' to see current state.")
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
        print("Usage: wfe load <path>")
        return
    session = Session.load_from(args[0])
    print(f"Loaded graph '{session.graph.name}'.")
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
        print("Usage: wfe add node|slot|edge ...")
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

    elif subcmd == "slot":
        if len(args) < 4:
            print("Usage: wfe add slot <node-id> <name> <type> [value]")
            return
        node_id, name, type_ = args[1], args[2], args[3]
        value = " ".join(args[4:]) if len(args) > 4 else None
        session.graph.add_slot(node_id, name, type_, value)
        session.persist()
        print(f"Added slot '{name}' to {node_id}.")
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
        print(f"Unknown: add {subcmd}. Use: add node | add slot | add edge")


def _cmd_remove(args: list[str]) -> None:
    if not args:
        print("Usage: wfe remove node|slot|edge ...")
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

    elif subcmd == "slot":
        if len(args) < 3:
            print("Usage: wfe remove slot <node-id> <name>")
            return
        session.graph.remove_slot(args[1], args[2])
        session.persist()
        print(f"Removed slot '{args[2]}' from {args[1]}.")
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
        print(f"Unknown: remove {subcmd}. Use: remove node | remove slot | remove edge")


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


if __name__ == "__main__":
    main()
