"""CLI entry point for the workflow engine.

REQ-WFE-026: Command-line entry point that creates or loads a graph and
positions the user at the home node.
"""

from __future__ import annotations

import sys
from pathlib import Path

from wfe.graph import (
    CycleError,
    Graph,
    HomeNodeError,
    ImmutableGraphError,
)
from wfe.persistence import load, save
from wfe.render import render_view
from wfe.session import NavigationError, Session


HELP_TEXT = """
Commands:
  view                          Show current node
  home                          Jump to home node
  go <node-id>                  Navigate to a connected node

  add node [name]               Create a new node (optional name prefix)
  remove node <node-id>         Delete a node
  add slot <node-id> <name> <type> [value]  Add a slot to a node
  remove slot <node-id> <name>  Remove a slot from a node
  add edge <source> <target> [condition]    Create an edge
  remove edge <source> <target> Remove an edge

  commit                        Freeze the graph (draft -> committed)
  checkout                      Create a draft copy (committed -> draft)
  save [path]                   Save graph to YAML
  load <path>                   Load graph from YAML

  nodes                         List all nodes
  help                          Show this help
  quit                          Exit
""".strip()


def main(args: list[str] | None = None) -> None:
    args = args or sys.argv[1:]

    if args and not args[0].startswith("-"):
        # Load existing graph
        path = Path(args[0])
        if path.exists():
            graph = load(path)
            print(f"Loaded graph '{graph.name}' from {path}")
        else:
            print(f"File not found: {path}")
            sys.exit(1)
    elif args and args[0] in ("--new", "-n"):
        name = args[1] if len(args) > 1 else "untitled"
        graph = Graph(name=name)
        print(f"Created new graph '{name}'")
    else:
        graph = Graph(name="untitled")
        print("Created new graph 'untitled'")

    session = Session(graph)
    print()
    print(render_view(session))
    print()

    _repl(session)


def _repl(session: Session) -> None:
    """Interactive command loop."""
    while True:
        try:
            prompt = f"{session.current_node.id}> "
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()

        try:
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "help":
                print(HELP_TEXT)
            elif cmd == "view":
                print(render_view(session))
            elif cmd == "home":
                session.home()
                print(render_view(session))
            elif cmd == "go":
                if len(parts) < 2:
                    print("Usage: go <node-id>")
                    continue
                session.go(parts[1])
                print(render_view(session))
            elif cmd == "nodes":
                _cmd_nodes(session)
            elif cmd == "add":
                _cmd_add(session, parts[1:])
            elif cmd == "remove":
                _cmd_remove(session, parts[1:])
            elif cmd == "commit":
                session.graph.commit()
                print("Graph committed. Structure is now frozen.")
                print(render_view(session))
            elif cmd == "checkout":
                session.graph = session.graph.checkout()
                session.current_node_id = session.graph.home_id
                print("Checked out draft copy. You are at the home node.")
                print(render_view(session))
            elif cmd == "save":
                path = parts[1] if len(parts) > 1 else f"{session.graph.name}.yaml"
                save(session.graph, path)
                print(f"Saved to {path}")
            elif cmd == "load":
                if len(parts) < 2:
                    print("Usage: load <path>")
                    continue
                session.graph = load(parts[1])
                session.current_node_id = session.graph.home_id
                print(f"Loaded graph '{session.graph.name}'. You are at the home node.")
                print(render_view(session))
            else:
                print(f"Unknown command: {cmd}. Type 'help' for commands.")
        except (
            ImmutableGraphError,
            CycleError,
            HomeNodeError,
            NavigationError,
            KeyError,
            ValueError,
        ) as e:
            print(f"Error: {e}")


def _cmd_nodes(session: Session) -> None:
    """List all nodes in the graph."""
    graph = session.graph
    for nid, node in graph.nodes.items():
        markers = []
        if nid == graph.home_id:
            markers.append("HOME")
        if nid == session.current_node_id:
            markers.append("HERE")
        suffix = f"  [{', '.join(markers)}]" if markers else ""
        slots = len(node.slots)
        edges = len(node.edges)
        print(f"  {nid}  ({slots} slots, {edges} edges){suffix}")


def _cmd_add(session: Session, args: list[str]) -> None:
    """Handle 'add node|slot|edge' commands."""
    if not args:
        print("Usage: add node|slot|edge ...")
        return

    subcmd = args[0].lower()
    if subcmd == "node":
        name = args[1] if len(args) > 1 else None
        node = session.graph.add_node(name)
        print(f"Created node: {node.id}")
    elif subcmd == "slot":
        if len(args) < 4:
            print("Usage: add slot <node-id> <name> <type> [value]")
            return
        node_id, name, type_ = args[1], args[2], args[3]
        value = args[4] if len(args) > 4 else None
        session.graph.add_slot(node_id, name, type_, value)
        print(f"Added slot '{name}' to {node_id}")
    elif subcmd == "edge":
        if len(args) < 3:
            print("Usage: add edge <source> <target> [condition]")
            return
        source, target = args[1], args[2]
        condition = " ".join(args[3:]) if len(args) > 3 else None
        session.graph.add_edge(source, target, condition)
        print(f"Created edge: {source} -> {target}")
    else:
        print(f"Unknown: add {subcmd}. Try: add node|slot|edge")


def _cmd_remove(session: Session, args: list[str]) -> None:
    """Handle 'remove node|slot|edge' commands."""
    if not args:
        print("Usage: remove node|slot|edge ...")
        return

    subcmd = args[0].lower()
    if subcmd == "node":
        if len(args) < 2:
            print("Usage: remove node <node-id>")
            return
        session.graph.remove_node(args[1])
        # If we deleted the node we were on, go home
        if session.current_node_id not in session.graph.nodes:
            session.current_node_id = session.graph.home_id
        print(f"Removed node: {args[1]}")
    elif subcmd == "slot":
        if len(args) < 3:
            print("Usage: remove slot <node-id> <name>")
            return
        session.graph.remove_slot(args[1], args[2])
        print(f"Removed slot '{args[2]}' from {args[1]}")
    elif subcmd == "edge":
        if len(args) < 3:
            print("Usage: remove edge <source> <target>")
            return
        session.graph.remove_edge(args[1], args[2])
        print(f"Removed edge: {args[1]} -> {args[2]}")
    else:
        print(f"Unknown: remove {subcmd}. Try: remove node|slot|edge")


if __name__ == "__main__":
    main()
