"""Compile a workflow graph into a structured markdown document.

Pure convention — no domain knowledge required:
  - All nodes sharing the same template_id form one group, rendered as a
    single markdown table (rows = nodes in BFS order, columns = fields)
  - Nodes with no template_id render as individual sections
  - Column headers are derived from field names (snake_case → Title Case)
  - Section headings use the node's prompt (first line) or a label from its ID

Any workflow graph can be compiled. Document structure emerges entirely from
graph topology and template provenance — no per-workflow configuration needed.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wfe.graph import Graph, Node


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


def _node_label(node: "Node") -> str:
    """Derive a display label from prompt or node ID."""
    if node.prompt:
        return node.prompt.splitlines()[0].strip()
    # Strip UUID suffix: "define-a1b2c3d4" -> "define"
    parts = node.id.rsplit("-", 1)
    prefix = parts[0] if len(parts) == 2 and len(parts[1]) == 8 else node.id
    return prefix.replace("-", " ").title()


def _col(name: str) -> str:
    return name.replace("_", " ").title()


def _fv(node: "Node", name: str) -> str:
    f = node.fields.get(name)
    if f is None or f.value is None:
        return ""
    if isinstance(f.value, list):
        return "; ".join(str(v) for v in f.value)
    return str(f.value)


def _render_table(template_id: str, nodes: list["Node"]) -> list[str]:
    if not nodes:
        return []
    field_names = list(nodes[0].fields.keys())
    headers = [_col(n) for n in field_names]
    sep = ["---"] * len(headers)

    lines = [f"### {_col(template_id)}", ""]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(sep) + " |")
    for node in nodes:
        lines.append("| " + " | ".join(_fv(node, fn) for fn in field_names) + " |")
    lines.append("")
    return lines


def _render_section(node: "Node") -> list[str]:
    label = _node_label(node)
    fields_with_values = [(n, f) for n, f in node.fields.items() if f.value is not None]

    if not fields_with_values and not node.prompt:
        return []  # Skip empty nodes

    lines = [f"### {label}", ""]
    if fields_with_values:
        for fname, f in fields_with_values:
            val = _fv(node, fname)
            if len(fields_with_values) == 1:
                lines.append(val)
            else:
                lines.append(f"**{_col(fname)}:** {val}")
            lines.append("")
    elif node.prompt:
        lines.append(node.prompt)
        lines.append("")
    return lines


def compile_graph(graph: "Graph") -> str:
    """Render a workflow graph as a structured markdown document."""
    order = _bfs(graph)

    # Group nodes: all same-template nodes → one table; templateless → individual sections
    # Preserve BFS first-encounter ordering for group position in output
    groups: list[tuple[str | None, list["Node"]]] = []
    template_index: dict[str, int] = {}

    for nid in order:
        node = graph.nodes[nid]
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
            lines.extend(_render_section(nodes[0]))
        else:
            lines.extend(_render_table(tid, nodes))

    lines.append("---")
    return "\n".join(lines)
