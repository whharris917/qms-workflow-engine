"""Action — a component that executes a function with side effects.

Unlike other components, Action is imperative: the user explicitly
triggers it. The action_fn receives sibling context, the Store, and the
current scope, enabling controlled writes to other components' state.

Preconditions gate execution. When confirm=True, the action requires a
two-step arm-then-confirm sequence. Results are stored for display.

writes_to declares which sibling keys the action may modify. This is
declarative documentation — not enforced at runtime — but enables
future dependency analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.component import Component
from engine.sibling_ref import SiblingRef
from engine.store import Store
from engine.templates import render_template


class DisabledAffordance(Affordance):
    """An affordance rendered as a disabled button with a message."""

    def __init__(self, label: str, message: str = ""):
        super().__init__(label=label, method="POST", url="", body={})
        self.message = message

    def _render_hints(self) -> dict:
        return {"type": "disabled_button", "message": self.message}


@dataclass
class Action(Component):
    """A button that executes a function with access to sibling state and the store."""
    form = "action"
    _callable_fields = ("action_fn", "precondition_fn")

    action_label: str = "Execute"
    action_fn: Callable[[dict, Store, str], dict] | None = None
    depends_on: "list[str | SiblingRef]" = field(default_factory=list)
    precondition_fn: Callable[[dict], bool] | None = None
    precondition_message: str = "Precondition not met."
    confirm: bool = False
    writes_to: list[str] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        if self.depends_on:
            self.depends_on = SiblingRef.coerce_many(self.depends_on)

    def _sibling_refs(self) -> list[SiblingRef]:
        return [r for r in self.depends_on if isinstance(r, SiblingRef)]

    @property
    def is_complete(self) -> bool:
        return True

    def _gather_context(self) -> dict:
        if self._store is None:
            return {}
        return {k: self._store.get(self._scope, k) for k in self.depends_on}

    @property
    def _enabled(self) -> bool:
        if self.precondition_fn is None:
            return True
        return self.precondition_fn(self._gather_context())

    @property
    def _armed(self) -> bool:
        val = self.value
        return isinstance(val, dict) and val.get("status") == "armed"

    def _serialize_state(self) -> dict:
        state = self._base_state() | {
            "enabled": self._enabled,
            "value": self.value,
        }
        if self.depends_on:
            state["depends_on"] = self.depends_on
        if not self._enabled:
            state["precondition_message"] = self.precondition_message
        if self.writes_to:
            state["writes_to"] = self.writes_to
        return state

    def get_affordances(self) -> list[Affordance]:
        if not self._enabled:
            return [DisabledAffordance(
                label=self.action_label,
                message=self.precondition_message,
            )]

        if self.confirm and self._armed:
            return [
                SimpleButtonAffordance(
                    label="Confirm",
                    method="POST",
                    url=self.url,
                    body={"action": "confirm"},
                    instruction="Confirm execution.",
                ),
                SimpleButtonAffordance(
                    label="Cancel",
                    method="POST",
                    url=self.url,
                    body={"action": "cancel"},
                    instruction="Cancel the armed action.",
                ),
            ]

        return [SimpleButtonAffordance(
            label=self.action_label,
            method="POST",
            url=self.url,
            body={"action": "execute"},
            instruction=self.instruction,
        )]

    def _execute(self) -> dict:
        context = self._gather_context()
        # Re-check precondition at execution time
        if self.precondition_fn and not self.precondition_fn(context):
            result = self.serialize()
            result["error"] = self.precondition_message
            result["failed_action"] = "execute"
            return result
        try:
            fn_result = self.action_fn(context, self._store, self._scope)
            # Strip structural_actions from stored result — it's internal plumbing
            stored_result = fn_result
            if isinstance(fn_result, dict) and "structural_actions" in fn_result:
                stored_result = {k: v for k, v in fn_result.items() if k != "structural_actions"}
            self._store.set(self._scope, self.key, {
                "status": "success",
                "result": stored_result,
                "executed_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as e:
            self._store.set(self._scope, self.key, {
                "status": "error",
                "error": str(e),
                "executed_at": datetime.now(timezone.utc).isoformat(),
            })
        result = self.serialize()
        # Pass structural actions up to the page (Phase E)
        if isinstance(fn_result, dict) and "structural_actions" in fn_result:
            result["_structural_actions"] = fn_result["structural_actions"]
        return result

    def render_from_data(self, data: dict) -> str:
        return render_template("action.html", data=data, ef=self,
                               url_prefix=self._url_prefix)

    _actions = {
        "execute": "_do_execute",
        "confirm": "_do_confirm",
        "cancel": "_do_cancel",
    }

    def _do_execute(self, body: dict) -> dict:
        if self.confirm:
            self._store.set(self._scope, self.key, {"status": "armed"})
            return self.serialize()
        return self._execute()

    def _do_confirm(self, body: dict) -> dict:
        return self._execute()

    def _do_cancel(self, body: dict) -> dict:
        self._store.set(self._scope, self.key, {"status": "cancelled"})
        return self.serialize()
