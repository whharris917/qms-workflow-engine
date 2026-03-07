"""Session persistence - tracks current graph and position between CLI invocations.

REQ-WFE-019: Current node context.
REQ-WFE-021: Jump to home.
REQ-WFE-030: Advance through the graph by evaluating outgoing edges.

Multi-agent isolation:
    Each agent sets WFE_SESSION=<id> in its environment. All session state
    (graph copy, session.json, form.yaml, target graphs) is isolated under
    .wfe/sessions/<id>/. Agents on different workflows never share state.

    If WFE_SESSION is unset, the session ID defaults to 'default', preserving
    single-agent behaviour.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from wfe.graph import Graph, GraphState
from wfe.hooks import HookContext, fire
from wfe.persistence import load, save


_BASE_DIR = Path(".wfe")


def _get_session_id() -> str:
    """Return the active session ID from WFE_SESSION env var, or 'default'."""
    return os.environ.get("WFE_SESSION", "default")


def _session_dir() -> Path:
    """Return the session-specific working directory for the current process."""
    return _BASE_DIR / "sessions" / _get_session_id()


class NoSessionError(Exception):
    """No active session exists."""


class NavigationError(Exception):
    """Navigation is not possible."""


class Session:
    """Persistent session state - survives between CLI invocations."""

    def __init__(
        self,
        graph: Graph,
        graph_path: Path,
        current_node_id: str,
        workspace: dict[str, Any] | None = None,
        session_dir: Path | None = None,
    ):
        self.graph = graph
        self.graph_path = graph_path
        self.current_node_id = current_node_id
        self.workspace: dict[str, Any] = workspace or {}
        self.session_dir: Path = session_dir or _session_dir()
        self._templates = None  # Lazy-loaded TemplateLibrary
        self._db = None         # Lazy-loaded MockDatabase

    @property
    def current_node(self):
        return self.graph.nodes[self.current_node_id]

    @property
    def is_construction_mode(self) -> bool:
        return self.graph.state == GraphState.DRAFT

    @property
    def templates(self):
        if self._templates is None:
            from wfe.template import TemplateLibrary
            self._templates = TemplateLibrary()
        return self._templates

    @property
    def db(self):
        if self._db is None:
            from wfe.database import MockDatabase
            self._db = MockDatabase()
        return self._db

    def _make_ctx(self) -> HookContext:
        # Expose session dir to hooks via workspace so they write to the right place
        self.workspace["_session_dir"] = str(self.session_dir)
        return HookContext(
            current_node=self.current_node,
            graph=self.graph,
            workspace=self.workspace,
            templates=self.templates,
            db=self.db,
        )

    def _fire_hooks(self, hook_names: list[str], ctx: HookContext) -> None:
        """Fire hooks; raise NavigationError if any block."""
        if not hook_names:
            return
        result = fire(hook_names, ctx)
        if not result.allowed:
            raise NavigationError(result.message)

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

        edge = next((e for e in node.edges if e.target == target_id), None)
        ctx = self._make_ctx()
        self._fire_hooks(node.exit_hooks, ctx)
        if edge:
            self._fire_hooks(edge.traverse_hooks, ctx)

        self.current_node_id = target_id
        ctx.current_node = self.current_node
        self._fire_hooks(self.current_node.enter_hooks, ctx)

    def home(self) -> None:
        """Jump to home node. (REQ-WFE-021)"""
        self.current_node_id = self.graph.home_id

    def fill(self, field_name: str, value: str) -> None:
        """Fill a field on the current node during execution. (REQ-WFE-027)"""
        self.graph.fill_field(self.current_node_id, field_name, value)

    def advance(self) -> str:
        """Evaluate outgoing edges and move to the next node. (REQ-WFE-030)

        Returns the target node ID navigated to.
        Raises NavigationError if zero or multiple edges are true.
        """
        true_edges = self.graph.evaluate_edges(self.current_node_id)
        if not true_edges:
            raise NavigationError(
                "No outgoing edges evaluate to true. Fill required fields first."
            )
        if len(true_edges) > 1:
            targets = ", ".join(e.target for e in true_edges)
            raise NavigationError(
                f"Multiple edges are true ({targets}). Use 'wfe go <id>' to choose."
            )

        edge = true_edges[0]
        target_id = edge.target
        node = self.current_node
        ctx = self._make_ctx()
        self._fire_hooks(node.exit_hooks, ctx)
        self._fire_hooks(edge.traverse_hooks, ctx)

        self.current_node_id = target_id
        ctx.current_node = self.current_node
        self._fire_hooks(self.current_node.enter_hooks, ctx)

        return target_id

    def persist(self) -> None:
        """Save session state and graph to disk."""
        self.session_dir.mkdir(parents=True, exist_ok=True)
        save(self.graph, self.graph_path)
        data = {
            "graph_path": str(self.graph_path),
            "current_node": self.current_node_id,
            "workspace": self.workspace,
        }
        (self.session_dir / "session.json").write_text(json.dumps(data, indent=2))

    @classmethod
    def create(cls, name: str) -> "Session":
        """Create a new graph and session."""
        sd = _session_dir()
        sd.mkdir(parents=True, exist_ok=True)
        graph = Graph(name=name)
        graph_path = sd / f"{name}.yaml"
        session = cls(graph, graph_path, graph.home_id, session_dir=sd)
        session.persist()
        return session

    @classmethod
    def resume(cls) -> "Session":
        """Resume the current session from disk."""
        sd = _session_dir()
        session_file = sd / "session.json"
        if not session_file.exists():
            sid = _get_session_id()
            hint = "" if sid == "default" else f" (WFE_SESSION={sid})"
            raise NoSessionError(
                f"No active session{hint}. Use 'wfe load <workflow>' to start one."
            )
        data = json.loads(session_file.read_text())
        graph_path = Path(data["graph_path"])
        if not graph_path.exists():
            raise NoSessionError(f"Graph file not found: {graph_path}")
        graph = load(graph_path)
        current_node = data["current_node"]
        if current_node not in graph.nodes:
            current_node = graph.home_id
        workspace = data.get("workspace", {})
        return cls(graph, graph_path, current_node, workspace=workspace, session_dir=sd)

    @classmethod
    def load_from(cls, path: str) -> "Session":
        """Load a graph from a specific path and make it the active session.

        The session always works from a copy in the session dir so the source
        file (e.g. a workflow in workflows/) is never overwritten.
        """
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(f"File not found: {path}")
        graph = load(source)
        sd = _session_dir()
        sd.mkdir(parents=True, exist_ok=True)
        working_path = sd / source.name
        session = cls(graph, working_path, graph.home_id, session_dir=sd)
        session.persist()
        return session
