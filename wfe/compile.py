"""Compile a workflow graph into a QMS CR-style markdown document.

Convention for CR workflows:
  - The "define" node has a 'title', 'cr_id', or 'purpose' field.
    It holds the pre-execution sections (1-9) as named string fields.
  - EI nodes have a 'task_description' field. They become rows in the
    execution table (section 10). BFS traversal from home determines order.
  - The "done" node is the last non-EI, non-define node with substantive
    content. Its 'execution_summary' field fills section 11.

Partial execution is supported: EI nodes with no 'outcome' show pending rows.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wfe.graph import Graph, Node


# Ordered mapping: field name on the define node -> section header
_SECTION_FIELDS = [
    ("purpose",             "## 1. Purpose"),
    ("scope",               "## 2. Scope"),
    ("current_state",       "## 3. Current State"),
    ("proposed_state",      "## 4. Proposed State"),
    ("change_description",  "## 5. Change Description"),
    ("justification",       "## 6. Justification"),
    ("impact_assessment",   "## 7. Impact Assessment"),
    ("testing_summary",     "## 8. Testing Summary"),
    ("implementation_plan", "## 9. Implementation Plan"),
]


def _fv(node: "Node", name: str) -> str:
    """Get a field's string value, or empty string if absent/empty."""
    f = node.fields.get(name)
    if f is None or f.value is None:
        return ""
    if isinstance(f.value, list):
        return "\n".join(str(v) for v in f.value)
    return str(f.value)


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


def _is_ei(node: "Node") -> bool:
    return "task_description" in node.fields


def _is_define(node: "Node") -> bool:
    return any(f in node.fields for f in ("title", "cr_id", "purpose"))


def _vr_col(node: "Node") -> str:
    f = node.fields.get("vr_required")
    if f is None or f.value is None:
        return ""
    return "Yes" if str(f.value).lower() in ("true", "yes", "1") else ""


def compile_graph(graph: "Graph") -> str:
    """Render a workflow graph as a QMS CR markdown document.

    Works on any loaded graph. Produces useful output for CR-type workflows
    (those with a define node and ei-template nodes) and a skeleton for others.
    """
    order = _bfs(graph)

    define_node = None
    ei_nodes: list["Node"] = []
    done_node = None

    for nid in order:
        node = graph.nodes[nid]
        if _is_ei(node):
            ei_nodes.append(node)
        elif _is_define(node):
            define_node = node
        elif node.fields or node.enter_hooks or node.exit_hooks:
            done_node = node  # Last substantive non-EI, non-define node

    # Document identity
    if define_node:
        cr_id = _fv(define_node, "cr_id") or graph.name
        title = _fv(define_node, "title") or graph.name
        revision_summary = _fv(define_node, "revision_summary")
    else:
        cr_id = graph.name
        title = graph.name
        revision_summary = ""

    lines: list[str] = []

    # YAML front matter
    lines += ["---", f"title: {title}"]
    if revision_summary:
        lines.append(f"revision_summary: {revision_summary}")
    lines += ["---", ""]

    # Document title
    lines += [f"# {cr_id}: {title}", ""]

    # Sections 1-9
    for field_name, header in _SECTION_FIELDS:
        content = _fv(define_node, field_name) if define_node else ""
        lines += [header, "", content if content else "*[TBD]*", "", "---", ""]

    # Section 10: Execution table
    lines += [
        "## 10. Execution",
        "",
        "| EI | Task Description | VR | Execution Summary | Task Outcome | Performed By - Date |",
        "|----|------------------|----|-------------------|--------------|---------------------|",
    ]
    for i, node in enumerate(ei_nodes, start=1):
        task = _fv(node, "task_description")
        vr = _vr_col(node)
        summary = _fv(node, "execution_summary")
        outcome = _fv(node, "outcome")
        performer = _fv(node, "performed_by")
        date = _fv(node, "date")
        pbd = f"{performer} - {date}" if performer and date else performer or date
        lines.append(f"| EI-{i} | {task} | {vr} | {summary} | {outcome} | {pbd} |")

    lines += [
        "",
        "---",
        "",
        "### Execution Comments",
        "",
        "| Comment | Performed By - Date |",
        "|---------|---------------------|",
        "",
        "---",
        "",
    ]

    # Section 11: Execution Summary
    exec_summary = _fv(done_node, "execution_summary") if done_node else ""
    lines += ["## 11. Execution Summary", "", exec_summary if exec_summary else "*[TBD]*", "", "---", ""]

    # Section 12: References
    refs = ""
    if done_node:
        refs = _fv(done_node, "references")
    if not refs and define_node:
        refs = _fv(define_node, "references")
    lines += ["## 12. References", "", refs if refs else "*[TBD]*", "", "---", "", "**END OF DOCUMENT**"]

    return "\n".join(lines)
