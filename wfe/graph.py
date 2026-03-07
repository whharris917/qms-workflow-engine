"""Graph primitives and DAG operations.

REQ-WFE-001 through REQ-WFE-018: Field, Node, Edge, Graph with lifecycle,
construction operations, and DAG invariant enforcement.
REQ-WFE-027 through REQ-WFE-030: Execution mode - field-filling and edge evaluation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class GraphState(Enum):
    DRAFT = "draft"
    COMMITTED = "committed"


@dataclass
class Field:
    """Atomic unit of data within a node. (REQ-WFE-001)"""

    name: str
    type: str
    value: Any = None
    writable: bool = True
    parameter: bool = False  # True if this field was a template parameter


@dataclass
class Edge:
    """Conditional connection from one node to another. (REQ-WFE-003)"""

    target: str  # Node ID
    condition: Optional[str] = None
    traverse_hooks: list[str] = field(default_factory=list)


@dataclass
class Node:
    """A step in a workflow. (REQ-WFE-002)"""

    id: str
    fields: dict[str, Field] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    prompt: Optional[str] = None
    enter_hooks: list[str] = field(default_factory=list)
    exit_hooks: list[str] = field(default_factory=list)
    template_id: Optional[str] = None  # Set when instantiated from a template
    label: Optional[str] = None        # Display label for compiled output


class ImmutableGraphError(Exception):
    """Raised when a construction operation is attempted on a committed graph."""


class CycleError(Exception):
    """Raised when an edge would create a cycle."""


class HomeNodeError(Exception):
    """Raised when attempting to delete the home node."""


class Graph:
    """A directed acyclic graph with lifecycle state.

    REQ-WFE-004: Acyclic invariant.
    REQ-WFE-005: Exactly one home node.
    REQ-WFE-006/007: Lifecycle state, new graphs start as draft with home node.
    """

    def __init__(self, name: str = "untitled"):
        self.name = name
        self.state = GraphState.DRAFT
        self.nodes: dict[str, Node] = {}
        # Create home node (REQ-WFE-005, REQ-WFE-007)
        self.home_id = self._make_id("home")
        self.nodes[self.home_id] = Node(id=self.home_id)

    def _make_id(self, prefix: str = "node") -> str:
        short = uuid.uuid4().hex[:8]
        return f"{prefix}-{short}"

    def _require_draft(self) -> None:
        """REQ-WFE-010: Reject construction operations on committed graphs."""
        if self.state == GraphState.COMMITTED:
            raise ImmutableGraphError(
                "Cannot modify a committed graph. Check it out first."
            )

    def _has_cycle_with(self, source: str, target: str) -> bool:
        """Check if adding an edge source->target would create a cycle.

        A cycle exists if target can already reach source via existing edges.
        """
        visited = set()
        stack = [target]
        while stack:
            current = stack.pop()
            if current == source:
                return True
            if current in visited:
                continue
            visited.add(current)
            if current in self.nodes:
                for edge in self.nodes[current].edges:
                    stack.append(edge.target)
        return False

    # --- Lifecycle (REQ-WFE-008, REQ-WFE-009) ---

    def commit(self) -> None:
        """Freeze the graph structure. (REQ-WFE-008)"""
        self._require_draft()
        self.state = GraphState.COMMITTED

    def checkout(self) -> "Graph":
        """Produce a draft copy for editing. (REQ-WFE-009)"""
        if self.state != GraphState.COMMITTED:
            raise ValueError("Only committed graphs can be checked out.")
        copy = Graph.__new__(Graph)
        copy.name = self.name
        copy.state = GraphState.DRAFT
        copy.home_id = self.home_id
        copy.nodes = {}
        for nid, node in self.nodes.items():
            copy.nodes[nid] = Node(
                id=node.id,
                fields={
                    k: Field(f.name, f.type, f.value, f.writable, f.parameter)
                    for k, f in node.fields.items()
                },
                edges=[
                    Edge(e.target, e.condition, list(e.traverse_hooks))
                    for e in node.edges
                ],
                prompt=node.prompt,
                enter_hooks=list(node.enter_hooks),
                exit_hooks=list(node.exit_hooks),
                template_id=node.template_id,
                label=node.label,
            )
        return copy

    # --- Construction: Nodes (REQ-WFE-011, REQ-WFE-012, REQ-WFE-013) ---

    def add_node(self, name: Optional[str] = None) -> Node:
        """Create a new node. (REQ-WFE-011)"""
        self._require_draft()
        nid = self._make_id(name or "node")
        node = Node(id=nid)
        self.nodes[nid] = node
        return node

    def remove_node(self, node_id: str) -> None:
        """Delete a node and all edges referencing it. (REQ-WFE-012, REQ-WFE-013)"""
        self._require_draft()
        if node_id == self.home_id:
            raise HomeNodeError("Cannot delete the home node.")
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        del self.nodes[node_id]
        # Remove edges targeting the deleted node from all other nodes
        for node in self.nodes.values():
            node.edges = [e for e in node.edges if e.target != node_id]

    # --- Construction: Fields (REQ-WFE-014, REQ-WFE-015) ---

    def add_field(
        self,
        node_id: str,
        name: str,
        type: str,
        value: Any = None,
        writable: bool = True,
        parameter: bool = False,
    ) -> Field:
        """Add a field to a node. (REQ-WFE-014)"""
        self._require_draft()
        node = self._get_node(node_id)
        if name in node.fields:
            raise ValueError(f"Field '{name}' already exists on node '{node_id}'.")
        f = Field(name=name, type=type, value=value, writable=writable, parameter=parameter)
        node.fields[name] = f
        return f

    def remove_field(self, node_id: str, field_name: str) -> None:
        """Remove a field from a node. (REQ-WFE-015)"""
        self._require_draft()
        node = self._get_node(node_id)
        if field_name not in node.fields:
            raise KeyError(f"Field '{field_name}' not found on node '{node_id}'.")
        del node.fields[field_name]

    # --- Construction: Edges (REQ-WFE-016, REQ-WFE-017, REQ-WFE-018) ---

    def add_edge(
        self, source_id: str, target_id: str, condition: Optional[str] = None
    ) -> Edge:
        """Create an edge between two nodes. (REQ-WFE-016, REQ-WFE-017)"""
        self._require_draft()
        source = self._get_node(source_id)
        self._get_node(target_id)  # Validate target exists
        if self._has_cycle_with(source_id, target_id):
            raise CycleError(
                f"Edge {source_id} -> {target_id} would create a cycle."
            )
        edge = Edge(target=target_id, condition=condition)
        source.edges.append(edge)
        return edge

    def remove_edge(self, source_id: str, target_id: str) -> None:
        """Remove an edge. (REQ-WFE-018)"""
        self._require_draft()
        source = self._get_node(source_id)
        original_len = len(source.edges)
        source.edges = [e for e in source.edges if e.target != target_id]
        if len(source.edges) == original_len:
            raise KeyError(f"No edge from '{source_id}' to '{target_id}'.")

    # --- Execution: Field-filling and edge evaluation (REQ-WFE-027 through REQ-WFE-030) ---

    def fill_field(self, node_id: str, field_name: str, value: Any) -> None:
        """Set a field value during execution. Works on committed graphs. (REQ-WFE-027)"""
        node = self._get_node(node_id)
        if field_name not in node.fields:
            raise KeyError(f"Field '{field_name}' not found on node '{node_id}'.")
        if not node.fields[field_name].writable:
            raise ValueError(f"Field '{field_name}' is read-only.")
        node.fields[field_name].value = value

    def evaluate_edges(self, node_id: str) -> list:
        """Return edges from node whose conditions are satisfied. (REQ-WFE-028)"""
        node = self._get_node(node_id)
        return [e for e in node.edges if self._condition_satisfied(e.condition, node)]

    def _condition_satisfied(self, condition: Optional[str], node: Node) -> bool:
        """Evaluate a condition string against a node's fields. (REQ-WFE-029)

        Supports: no condition (always true), `name==value`, `name!=value`.
        """
        if not condition:
            return True
        if "==" in condition:
            name, expected = condition.split("==", 1)
            name, expected = name.strip(), expected.strip()
            actual = (
                str(node.fields[name].value)
                if name in node.fields and node.fields[name].value is not None
                else ""
            )
            return actual == expected
        if "!=" in condition:
            name, expected = condition.split("!=", 1)
            name, expected = name.strip(), expected.strip()
            actual = (
                str(node.fields[name].value)
                if name in node.fields and node.fields[name].value is not None
                else ""
            )
            return actual != expected
        return False

    # --- Helpers ---

    def _get_node(self, node_id: str) -> Node:
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        return self.nodes[node_id]

    def set_home(self, node_id: str) -> None:
        """Designate an existing node as the home node.

        If the previous home node is empty (no fields, edges, or hooks), it is
        removed. This allows build_node_chain to promote the first real node to
        home and discard the bare placeholder created by __init__.
        """
        self._require_draft()
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        old_home_id = self.home_id
        self.home_id = node_id
        if old_home_id and old_home_id != node_id and old_home_id in self.nodes:
            old = self.nodes[old_home_id]
            if not old.fields and not old.edges and not old.enter_hooks and not old.exit_hooks:
                del self.nodes[old_home_id]

    @property
    def home(self) -> Node:
        return self.nodes[self.home_id]
