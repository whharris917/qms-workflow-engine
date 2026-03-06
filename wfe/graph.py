"""Graph primitives and DAG operations.

REQ-WFE-001 through REQ-WFE-018: Slot, Node, Edge, Graph with lifecycle,
construction operations, and DAG invariant enforcement.
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
class Slot:
    """Atomic unit of data within a node. (REQ-WFE-001)"""

    name: str
    type: str
    value: Any = None
    writable: bool = True


@dataclass
class Edge:
    """Conditional connection from one node to another. (REQ-WFE-003)"""

    target: str  # Node ID
    condition: Optional[str] = None


@dataclass
class Node:
    """A step in a workflow. (REQ-WFE-002)"""

    id: str
    slots: dict[str, Slot] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    prompt: Optional[str] = None


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
                slots={k: Slot(s.name, s.type, s.value, s.writable) for k, s in node.slots.items()},
                edges=[Edge(e.target, e.condition) for e in node.edges],
                prompt=node.prompt,
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

    # --- Construction: Slots (REQ-WFE-014, REQ-WFE-015) ---

    def add_slot(self, node_id: str, name: str, type: str, value: Any = None, writable: bool = True) -> Slot:
        """Add a slot to a node. (REQ-WFE-014)"""
        self._require_draft()
        node = self._get_node(node_id)
        if name in node.slots:
            raise ValueError(f"Slot '{name}' already exists on node '{node_id}'.")
        slot = Slot(name=name, type=type, value=value, writable=writable)
        node.slots[name] = slot
        return slot

    def remove_slot(self, node_id: str, slot_name: str) -> None:
        """Remove a slot from a node. (REQ-WFE-015)"""
        self._require_draft()
        node = self._get_node(node_id)
        if slot_name not in node.slots:
            raise KeyError(f"Slot '{slot_name}' not found on node '{node_id}'.")
        del node.slots[slot_name]

    # --- Construction: Edges (REQ-WFE-016, REQ-WFE-017, REQ-WFE-018) ---

    def add_edge(self, source_id: str, target_id: str, condition: Optional[str] = None) -> Edge:
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

    # --- Helpers ---

    def _get_node(self, node_id: str) -> Node:
        if node_id not in self.nodes:
            raise KeyError(f"Node '{node_id}' not found.")
        return self.nodes[node_id]

    @property
    def home(self) -> Node:
        return self.nodes[self.home_id]
