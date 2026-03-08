"""Compile a workflow graph into a structured markdown document.

Pure convention — no domain knowledge required:
  - All nodes sharing the same template_id form one group, rendered as a
    single markdown table (rows = nodes in BFS order, columns = fields)
  - Nodes with no template_id render as individual sections
  - Column headers are derived from field names (snake_case → Title Case)
  - Section headings use the node's label or a label derived from its ID

Cell status conventions:
  - Workflow not in execution (no fields filled anywhere): [EXECUTABLE]
  - Pending node, prerequisites met: [READY]
  - Pending node, prerequisites not met: [BLOCKED]
  - Executed node, field intentionally blank or auto-managed: N/A

Any workflow graph can be compiled. Document structure emerges entirely from
graph topology and template provenance — no per-workflow configuration needed.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wfe.graph import Graph, Node


# ---------------------------------------------------------------------------
# Graph traversal
# ---------------------------------------------------------------------------

def _bfs(graph: "Graph") -> list[str]:
    """Return node IDs in BFS order from home, following all edges."""
    visited: list[str] = []
    seen: set[str] = set()
    q: deque[str] = deque([graph.home_id])
    while q:
        nid = q.popleft()
        if nid in seen:
            continue
        seen.add(nid)
        if nid in graph.nodes:
            visited.append(nid)
            for edge in graph.nodes[nid].edges:
                q.append(edge.target)
    return visited


def _build_reverse_edges(graph: "Graph") -> dict[str, list]:
    """Map each node ID to (source_node, edge) pairs of its incoming navigation edges.

    Subprocess edges (spawns_workflow set, target not in graph) are excluded —
    they don't represent graph navigation.
    """
    rev: dict[str, list] = {}
    for node in graph.nodes.values():
        for edge in node.edges:
            if edge.target in graph.nodes:  # navigation edge only
                rev.setdefault(edge.target, []).append((node, edge))
    return rev


# ---------------------------------------------------------------------------
# Execution state helpers
# ---------------------------------------------------------------------------

def _graph_in_execution(graph: "Graph") -> bool:
    """True if any writable field anywhere has a value (execution has started)."""
    return any(
        f.writable and f.value is not None
        for node in graph.nodes.values()
        for f in node.fields.values()
    )


def _node_executed(node: "Node") -> bool:
    """True if any writable field has a value — indicates the node was visited."""
    return any(f.writable and f.value is not None for f in node.fields.values())


def _node_ready(node: "Node", graph: "Graph", rev_edges: dict) -> bool:
    """True if at least one predecessor navigation edge is satisfied.

    Home node is always ready. All others require an executed predecessor
    whose outgoing edge condition is satisfied.
    """
    if node.id == graph.home_id:
        return True
    for source_node, edge in rev_edges.get(node.id, []):
        if _node_executed(source_node) and graph._condition_satisfied(edge.condition, source_node):
            return True
    return False


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _node_label(node: "Node") -> str:
    if node.label:
        return node.label
    parts = node.id.rsplit("-", 1)
    prefix = parts[0] if len(parts) == 2 and len(parts[1]) == 8 else node.id
    return prefix.replace("-", " ").title()


def _col(name: str) -> str:
    return name.replace("_", " ").title()


def _fv(node: "Node", name: str) -> str:
    """Raw field value as string, empty string if absent or None."""
    f = node.fields.get(name)
    if f is None or f.value is None:
        return ""
    if isinstance(f.value, list):
        return "; ".join(str(v) for v in f.value)
    return str(f.value)


def _cell(
    node: "Node",
    field_name: str,
    executed: bool,
    ready: bool,
    in_exec: bool,
) -> str:
    """Render a single table/section cell with execution-aware status."""
    f = node.fields.get(field_name)
    if f is None:
        return ""
    if f.value is not None:
        if isinstance(f.value, list):
            return "; ".join(str(v) for v in f.value)
        return str(f.value)
    # Blank field
    if not in_exec:
        return "[EXECUTABLE]" if f.writable else ""
    if executed or not f.writable:
        return "N/A"
    return "[READY]" if ready else "[BLOCKED]"


# ---------------------------------------------------------------------------
# Child workflow helpers
# ---------------------------------------------------------------------------

def _parse_child_ref(ref: str) -> tuple[str, str, str]:
    """Parse a child_workflows entry into (condition, display_id, link_path).

    Supported formats:
      "VAR-001"                              -> condition="", id="VAR-001", path=compiled/VAR-001.md
      "outcome==Fail::VAR-001"               -> condition="outcome==Fail", id="VAR-001", path=compiled/VAR-001.md
      "outcome==Fail::VAR-001::QMS/VAR/..."  -> condition="outcome==Fail", id="VAR-001", path=explicit
    """
    parts = ref.split("::")
    if len(parts) >= 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    if len(parts) == 2:
        cond, wf_id = parts[0].strip(), parts[1].strip()
        return cond, wf_id, f"compiled/{wf_id}.md"
    return "", ref.strip(), f"compiled/{ref.strip()}.md"


def _child_workflow_link(wf_ref: str) -> str:
    condition, display, path = _parse_child_ref(wf_ref)
    link = f"[{display}]({path})"
    return f"{condition}: {link}" if condition else link


def _potential_child_workflow_links(node: "Node") -> str:
    seen: set[str] = set()
    parts = []
    for edge in node.edges:
        wf = edge.spawns_workflow
        if wf and wf not in seen:
            seen.add(wf)
            cond = f"{edge.condition}: " if edge.condition else ""
            parts.append(f"{cond}[{wf.upper()}](compiled/{wf}.md)")
    return ", ".join(parts)


def _child_workflow_cell(node: "Node", executed: bool, in_exec: bool) -> str:
    """Return the Child Workflows column content."""
    if node.child_workflows:
        return ", ".join(_child_workflow_link(ref) for ref in node.child_workflows)
    has_subprocess_edges = any(e.spawns_workflow for e in node.edges)
    if not executed:
        return _potential_child_workflow_links(node)  # "" if no subprocess edges
    # Executed: N/A only if the node had subprocess potential (something could have spawned)
    return ("N/A" if in_exec else "") if has_subprocess_edges else ""


def _has_child_workflow_info(nodes: list["Node"]) -> bool:
    return any(
        node.child_workflows or any(e.spawns_workflow for e in node.edges)
        for node in nodes
    )


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _render_table(
    template_id: str,
    nodes: list["Node"],
    in_exec: bool,
    rev_edges: dict,
    graph: "Graph",
) -> list[str]:
    if not nodes:
        return []

    field_names = list(nodes[0].fields.keys())
    show_children = _has_child_workflow_info(nodes)
    headers = [_col(n) for n in field_names]
    if show_children:
        headers.append("Child Workflows")
    sep = ["---"] * len(headers)

    heading = nodes[0].label or _col(template_id)
    lines = [f"### {heading}", ""]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(sep) + " |")

    for node in nodes:
        executed = _node_executed(node)
        ready = _node_ready(node, graph, rev_edges) if in_exec and not executed else False
        row = [_cell(node, fn, executed, ready, in_exec) for fn in field_names]
        if show_children:
            row.append(_child_workflow_cell(node, executed, in_exec))
        lines.append("| " + " | ".join(row) + " |")

    lines.append("")
    return lines


def _render_section(
    node: "Node",
    in_exec: bool,
    rev_edges: dict,
    graph: "Graph",
) -> list[str]:
    label = _node_label(node)
    fields_with_values = [(n, f) for n, f in node.fields.items() if f.value is not None]
    executed = _node_executed(node)
    ready = _node_ready(node, graph, rev_edges) if in_exec and not executed else False
    children = _child_workflow_cell(node, executed, in_exec)

    if not fields_with_values and not children:
        if not node.fields:
            return []  # No fields defined — skip entirely
        # Section has fields but all blank — show status heading
        if not in_exec:
            status = "[EXECUTABLE]"
        elif executed:
            status = "N/A"
        elif ready:
            status = "[READY]"
        else:
            status = "[BLOCKED]"
        return [f"### {label}", "", status, ""]

    lines = [f"### {label}", ""]
    for fname, f in fields_with_values:
        val = _fv(node, fname)
        if len(fields_with_values) == 1 and not children:
            lines.append(val)
        elif f.block:
            lines.append(f"**{_col(fname)}**")
            lines.append("")
            lines.append(val)
        else:
            lines.append(f"**{_col(fname)}:** {val}")
        lines.append("")
    if children:
        lines.append(f"**Child Workflows:** {children}")
        lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compile_graph(graph: "Graph") -> str:
    """Render a workflow graph as a structured markdown document."""
    order = _bfs(graph)
    in_exec = _graph_in_execution(graph)
    rev_edges = _build_reverse_edges(graph)

    # Group nodes: same-template → one table; templateless → individual sections
    # Preserve BFS first-encounter ordering for group position in output
    groups: list[tuple[str | None, list["Node"]]] = []
    template_index: dict[str, int] = {}

    for nid in order:
        node = graph.nodes[nid]
        if node.scaffold:
            continue  # Scaffold nodes are authoring aids, not document content
        tid = node.template_id
        if tid is None:
            groups.append((None, [node]))
        elif tid in template_index:
            groups[template_index[tid]][1].append(node)
        else:
            template_index[tid] = len(groups)
            groups.append((tid, [node]))

    lines: list[str] = [f"# {graph.name}", ""]
    for tid, nodes in groups:
        if tid is None:
            lines.extend(_render_section(nodes[0], in_exec, rev_edges, graph))
        else:
            lines.extend(_render_table(tid, nodes, in_exec, rev_edges, graph))

    lines.append("---")
    return "\n".join(lines)
