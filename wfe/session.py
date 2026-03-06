"""Session persistence - tracks current graph and position between CLI invocations.

REQ-WFE-019: Current node context.
REQ-WFE-021: Jump to home.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from wfe.graph import Graph, GraphState
from wfe.persistence import load, save


SESSION_DIR = Path(".wfe")
SESSION_FILE = SESSION_DIR / "session.json"


class NoSessionError(Exception):
    """No active session exists."""


class NavigationError(Exception):
    """Navigation is not possible."""


class Session:
    """Persistent session state - survives between CLI invocations."""

    def __init__(self, graph: Graph, graph_path: Path, current_node_id: str):
        self.graph = graph
        self.graph_path = graph_path
        self.current_node_id = current_node_id

    @property
    def current_node(self):
        return self.graph.nodes[self.current_node_id]

    @property
    def is_construction_mode(self) -> bool:
        return self.graph.state == GraphState.DRAFT

    def go(self, target_id: str) -> None:
        """Navigate to a connected node. (REQ-WFE-020)"""
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
        """Jump to home node. (REQ-WFE-021)"""
        self.current_node_id = self.graph.home_id

    def persist(self) -> None:
        """Save session state and graph to disk."""
        SESSION_DIR.mkdir(exist_ok=True)
        save(self.graph, self.graph_path)
        data = {
            "graph_path": str(self.graph_path),
            "current_node": self.current_node_id,
        }
        SESSION_FILE.write_text(json.dumps(data, indent=2))

    @classmethod
    def create(cls, name: str) -> "Session":
        """Create a new graph and session."""
        SESSION_DIR.mkdir(exist_ok=True)
        graph = Graph(name=name)
        graph_path = SESSION_DIR / f"{name}.yaml"
        session = cls(graph, graph_path, graph.home_id)
        session.persist()
        return session

    @classmethod
    def resume(cls) -> "Session":
        """Resume the current session from disk."""
        if not SESSION_FILE.exists():
            raise NoSessionError(
                "No active session. Use 'wfe new <name>' to create a graph."
            )
        data = json.loads(SESSION_FILE.read_text())
        graph_path = Path(data["graph_path"])
        if not graph_path.exists():
            raise NoSessionError(f"Graph file not found: {graph_path}")
        graph = load(graph_path)
        current_node = data["current_node"]
        if current_node not in graph.nodes:
            current_node = graph.home_id
        return cls(graph, graph_path, current_node)

    @classmethod
    def load_from(cls, path: str) -> "Session":
        """Load a graph from a specific path and make it the active session."""
        graph_path = Path(path)
        if not graph_path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        graph = load(graph_path)
        session = cls(graph, graph_path, graph.home_id)
        session.persist()
        return session
