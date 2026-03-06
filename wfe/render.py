"""Render graph state as text for agent consumption.

REQ-WFE-022: Render current node with slots, edges, targets.
REQ-WFE-023: Indicate graph lifecycle state.
"""

from __future__ import annotations

from wfe.graph import Graph, GraphState, Node
from wfe.session import Session


def render_node(node: Node, graph: Graph) -> str:
    """Render a single node's details."""
    lines = []
    is_home = node.id == graph.home_id
    label = f"  [HOME]" if is_home else ""
    lines.append(f"Node: {node.id}{label}")

    if node.prompt:
        lines.append(f"Prompt: {node.prompt}")

    if node.slots:
        lines.append("Slots:")
        for slot in node.slots.values():
            val = repr(slot.value) if slot.value is not None else "(empty)"
            rw = "writable" if slot.writable else "read-only"
            lines.append(f"  {slot.name} [{slot.type}, {rw}]: {val}")
    else:
        lines.append("Slots: (none)")

    if node.edges:
        lines.append("Edges:")
        for edge in node.edges:
            target_node = graph.nodes.get(edge.target)
            target_label = target_node.id if target_node else f"{edge.target} (missing)"
            cond = f" when: {edge.condition}" if edge.condition else ""
            lines.append(f"  -> {target_label}{cond}")
    else:
        lines.append("Edges: (none)")

    return "\n".join(lines)


def render_view(session: Session) -> str:
    """Render the full view for the current session state. (REQ-WFE-022, REQ-WFE-023)"""
    graph = session.graph
    node = session.current_node

    lines = []
    # Header with graph name and state (REQ-WFE-023)
    state_label = graph.state.value.upper()
    mode = "construction" if session.is_construction_mode else "read-only"
    lines.append(f"=== {graph.name} ({state_label}) — {mode} mode ===")
    lines.append("")
    lines.append(render_node(node, graph))
    lines.append("")

    # Summary footer
    total = len(graph.nodes)
    lines.append(f"Graph: {total} node{'s' if total != 1 else ''}")

    return "\n".join(lines)
