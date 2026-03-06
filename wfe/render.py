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

    if node.prompt:
        lines.append(f"Prompt: {node.prompt}")

    # Slots
    if node.slots:
        lines.append("Slots:")
        for slot in node.slots.values():
            val = repr(slot.value) if slot.value is not None else "(empty)"
            rw = "writable" if slot.writable else "read-only"
            lines.append(f"  {slot.name} [{slot.type}, {rw}]: {val}")
    else:
        lines.append("Slots: (none)")

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
    lines.append(_available_actions(graph, node, current_node_id))

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


def _available_actions(graph: Graph, node: Node, current_node_id: str) -> str:
    """Build the context-sensitive 'Available' line."""
    actions = []

    # Navigation
    if node.edges:
        targets = [e.target for e in node.edges]
        if len(targets) == 1:
            actions.append(f"go {targets[0]}")
        else:
            actions.append("go <node-id>")
    if current_node_id != graph.home_id:
        actions.append("home")

    # Construction (draft only)
    if graph.state == GraphState.DRAFT:
        actions.extend(["add node", "add slot", "add edge", "remove node", "remove slot", "remove edge"])
        actions.append("commit")
    else:
        actions.append("checkout")

    # Always available
    actions.extend(["nodes", "save"])

    return "Available: " + " | ".join(actions)
