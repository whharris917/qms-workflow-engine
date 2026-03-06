"""Session — navigation and current node context.

REQ-WFE-019 through REQ-WFE-021: Current node tracking, edge navigation, home jump.
"""

from __future__ import annotations

from wfe.graph import Graph, GraphState


class NavigationError(Exception):
    """Raised when navigation is not possible."""


class Session:
    """Holds the transient state of a user interacting with a graph.

    REQ-WFE-019: Maintains current node context.
    """

    def __init__(self, graph: Graph):
        self.graph = graph
        self.current_node_id = graph.home_id

    @property
    def current_node(self):
        return self.graph.nodes[self.current_node_id]

    @property
    def is_construction_mode(self) -> bool:
        return self.graph.state == GraphState.DRAFT

    def go(self, target_id: str) -> None:
        """Navigate to a connected node by following an outgoing edge. (REQ-WFE-020)"""
        node = self.current_node
        reachable = {e.target for e in node.edges}
        if target_id not in reachable:
            raise NavigationError(
                f"No edge from '{self.current_node_id}' to '{target_id}'."
            )
        if target_id not in self.graph.nodes:
            raise NavigationError(f"Target node '{target_id}' does not exist.")
        self.current_node_id = target_id

    def home(self) -> None:
        """Jump directly to the home node. (REQ-WFE-021)"""
        self.current_node_id = self.graph.home_id
