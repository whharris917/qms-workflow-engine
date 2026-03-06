"""Render graph state as text with progressive disclosure.

REQ-WFE-022: Render current node with slots, edges, targets.
REQ-WFE-023: Indicate graph lifecycle state.

The rendered view IS the interface. Every output shows what you're looking at
and what you can do next. An agent should never need to ask for help.
"""

from __future__ import annotations

from wfe.graph import Graph, GraphState, Node


def render_view(graph: Graph, current_node_id: str) -> str:
    """Render the full view: current node + available actions."""
    node = graph.nodes[current_node_id]
    lines = []

    # Header
    state_label = graph.state.value.upper()
    mode = "construction" if graph.state == GraphState.DRAFT else "read-only"
    lines.append(f"=== {graph.name} ({state_label}) - {mode} mode ===")
    lines.append("")

    # Current node
    is_home = current_node_id == graph.home_id
    label = "  [HOME]" if is_home else ""
    lines.append(f"Node: {node.id}{label}")

    # Orientation hint: home node with no edges is the "blank canvas" state
    if is_home and not node.edges and graph.state == GraphState.DRAFT:
        lines.append("  This is the home node - the entry point for all navigation.")
        lines.append("  Start by adding child nodes, then connect them with edges.")

    if node.prompt:
        lines.append(f"Prompt: {node.prompt}")

    # Fields
    if node.fields:
        lines.append("Fields:")
        for f in node.fields.values():
            val = repr(f.value) if f.value is not None else "(empty)"
            rw = "writable" if f.writable else "read-only"
            lines.append(f"  {f.name} [{f.type}, {rw}]: {val}")
    else:
        lines.append("Fields: (none)")

    # Edges
    if node.edges:
        lines.append("Edges:")
        for edge in node.edges:
            target_node = graph.nodes.get(edge.target)
            target_label = target_node.id if target_node else f"{edge.target} (missing)"
            cond = f"  when: {edge.condition}" if edge.condition else ""
            lines.append(f"  -> {target_label}{cond}")
    else:
        lines.append("Edges: (none)")

    # Graph summary
    lines.append("")
    total = len(graph.nodes)
    lines.append(f"Graph: {total} node{'s' if total != 1 else ''}")

    # Available actions - progressive disclosure
    lines.append("")
    lines.extend(_available_actions(graph, node, current_node_id))

    return "\n".join(lines)


def render_nodes(graph: Graph, current_node_id: str) -> str:
    """Render a list of all nodes in the graph."""
    lines = []
    for nid, node in graph.nodes.items():
        markers = []
        if nid == graph.home_id:
            markers.append("HOME")
        if nid == current_node_id:
            markers.append("HERE")
        suffix = f"  [{', '.join(markers)}]" if markers else ""
        slots = len(node.slots)
        edges = len(node.edges)
        lines.append(f"  {nid}  ({slots} slots, {edges} edges){suffix}")
    return "\n".join(lines)


HELP_TEXT = """
Commands:
  wfe new <name>                               Create a new graph
  wfe load <name-or-path>                      Load a graph from .wfe/ or a YAML path
  wfe view                                     Show current node
  wfe nodes                                    List all nodes in the graph
  wfe home                                     Jump to the home node
  wfe go <node-id>                             Navigate to a connected node

  wfe add node [name]                          Create a new node (optional name prefix)
  wfe add field <node-id> <name> <type> [val]  Add a field to a node
  wfe add edge <source> <target> [condition]   Create an edge between nodes
  wfe remove node <node-id>                    Delete a node (home node cannot be deleted)
  wfe remove field <node-id> <name>            Remove a field from a node
  wfe remove edge <source> <target>            Remove an edge

  wfe set <node-id> <field-name> <value>       Set or update a field's value

  wfe fill <field-name> <value>                Fill a field on the current node (execution mode)
  wfe advance                                  Evaluate outgoing edges and move to the next node

  wfe commit                                   Freeze graph structure (draft -> committed)
  wfe checkout                                 Create a draft copy for editing (committed -> draft)
  wfe save [path]                              Save graph to .wfe/ or a specific path

  wfe help                                     Show this help

Field types: string, int, float, bool, or any label you choose.
Node IDs are assigned automatically (e.g., review-a1b2c3d4). Use 'wfe nodes' to list them.
Conditions on edges are free-form strings (e.g., "verdict==approved").
Edge conditions support == and != operators (e.g., "verdict!=rejected").
""".strip()


def _available_actions(graph: Graph, node: Node, current_node_id: str) -> list[str]:
    """Build context-sensitive available action lines, grouped by category."""
    nav = []
    construct = []
    execute = []
    lifecycle = []

    # Navigation: one go entry per outgoing edge (copyable IDs)
    for edge in node.edges:
        nav.append(f"go {edge.target}")
    if current_node_id != graph.home_id:
        nav.append("home")

    if graph.state == GraphState.DRAFT:
        # Construction: always available
        construct.append("add node <name>")
        construct.append(f"add field {current_node_id} <name> <type>")
        construct.append(f"add edge {current_node_id} <target-id>")

        # Removes only when there's something to remove
        if node.fields:
            construct.append(f"set {current_node_id} <field-name> <value>")
            construct.append(f"remove field {current_node_id} <name>")
        if node.edges:
            construct.append(f"remove edge {current_node_id} <target-id>")
        if len(graph.nodes) > 1 and current_node_id != graph.home_id:
            construct.append(f"remove node {current_node_id}")

        lifecycle.append("commit")
    else:
        # Execution: fill unfilled writable fields, advance if edges exist
        unfilled = [f for f in node.fields.values() if f.writable and f.value is None]
        for f in unfilled:
            execute.append(f"fill {f.name} <value>")
        if node.edges:
            execute.append("advance")

        lifecycle.append("checkout")

    lifecycle.extend(["nodes", "save", "help"])

    lines = []
    if nav:
        lines.append("Navigate: " + " | ".join(nav))
    if construct:
        lines.append("Construct: " + " | ".join(construct))
    if execute:
        lines.append("Execute: " + " | ".join(execute))
    lines.append("Graph: " + " | ".join(lifecycle))

    return lines
