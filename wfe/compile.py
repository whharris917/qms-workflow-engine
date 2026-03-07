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
    """Return the node's display label.

    Uses node.label if set, otherwise derives from the node ID.
    prompt is execution-time agent instruction, not document content — excluded.
    """
    if node.label:
        return node.label
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
    """Format a markdown link for an actual child workflow instance."""
    condition, display, path = _parse_child_ref(wf_ref)
    link = f"[{display}]({path})"
    return f"{condition}: {link}" if condition else link


def _potential_child_workflow_links(node: "Node") -> str:
    """Format potential child workflow links from outgoing subprocess edges."""
    seen: set[str] = set()
    parts = []
    for edge in node.edges:
        wf = edge.spawns_workflow
        if wf and wf not in seen:
            seen.add(wf)
            cond = f"{edge.condition}: " if edge.condition else ""
            parts.append(f"{cond}[{wf.upper()}](compiled/{wf}.md)")
    return ", ".join(parts)


def _node_executed(node: "Node") -> bool:
    """True if any writable field has a value — indicates the node was visited."""
    return any(f.writable and f.value is not None for f in node.fields.values())


def _child_workflow_cell(node: "Node") -> str:
    """Return the Child Workflows column content for a table row."""
    if node.child_workflows:
        return ", ".join(_child_workflow_link(ref) for ref in node.child_workflows)
    # Show potential pathways only for nodes not yet executed.
    # An executed node with empty child_workflows completed without spawning.
    if not _node_executed(node):
        return _potential_child_workflow_links(node)
    return ""


def _has_child_workflow_info(nodes: list["Node"]) -> bool:
    for node in nodes:
        if node.child_workflows:
            return True
        if any(e.spawns_workflow for e in node.edges):
            return True
    return False


def _render_table(template_id: str, nodes: list["Node"]) -> list[str]:
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
        row = [_fv(node, fn) for fn in field_names]
        if show_children:
            row.append(_child_workflow_cell(node))
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return lines


def _render_section(node: "Node") -> list[str]:
    label = _node_label(node)
    fields_with_values = [(n, f) for n, f in node.fields.items() if f.value is not None]
    children = _child_workflow_cell(node)

    if not fields_with_values and not children:
        return []  # Skip nodes with no document content

    lines = [f"### {label}", ""]
    for fname, f in fields_with_values:
        val = _fv(node, fname)
        if len(fields_with_values) == 1 and not children:
            lines.append(val)
        else:
            lines.append(f"**{_col(fname)}:** {val}")
        lines.append("")
    if children:
        lines.append(f"**Child Workflows:** {children}")
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
