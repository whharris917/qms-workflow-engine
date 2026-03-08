"""Hook dispatch infrastructure for the workflow engine.

Hooks are named functions that fire at three trigger points:
  - enter_node: when the engine moves INTO a node
  - exit_node: when the engine moves OUT OF a node
  - traverse_edge: before an edge is followed

Any hook can block the operation by returning HookResult(False, message).

Hook implementations are registered elsewhere via @register(). The engine
has no knowledge of what any hook does — it only dispatches by name.

To provide hook implementations, create a workflow_hooks.py file in the
working directory. The CLI will auto-load it on startup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from wfe.graph import Graph, Node

REGISTRY: dict[str, Callable] = {}


@dataclass
class HookResult:
    """Result of a hook invocation."""

    allowed: bool
    message: str = ""


@dataclass
class HookContext:
    """Context passed to hook functions."""

    current_node: Node
    graph: Graph
    workspace: dict[str, Any]
    templates: Any  # TemplateLibrary | None
    db: Any         # MockDatabase | None


def register(name: str):
    """Decorator to register a hook function by name."""
    def decorator(fn: Callable) -> Callable:
        REGISTRY[name] = fn
        return fn
    return decorator


def fire(hook_names: list[str], ctx: HookContext) -> HookResult:
    """Fire a sequence of hooks. Stops at the first blocking hook.

    Hook names may include colon-separated parameters: "name:p1:p2".
    Parameters are passed as positional arguments after ctx.
    """
    for raw in hook_names:
        parts = raw.split(":")
        name = parts[0]
        params = parts[1:]
        if name not in REGISTRY:
            return HookResult(False, f"Hook '{name}' not registered.")
        result = REGISTRY[name](ctx, *params)
        if not result.allowed:
            return result
    return HookResult(True)
