"""ActionForm — an eigenform that executes a function with side effects.

Unlike other eigenforms, ActionForm is imperative: the user explicitly
triggers it. The action_fn receives sibling context, the Store, and the
current scope, enabling controlled writes to other eigenforms' state.

Preconditions gate execution. When confirm=True, the action requires a
two-step arm-then-confirm sequence. Results are stored for display.

writes_to declares which sibling keys the action may modify. This is
declarative documentation — not enforced at runtime — but enables
future dependency analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from typing import Any, Callable

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.eigenform import Eigenform
from engine.store import Store


class DisabledAffordance(Affordance):
    """An affordance rendered as a disabled button with a message."""

    def __init__(self, label: str, message: str = ""):
        super().__init__(label=label, method="POST", url="", body={})
        self.message = message

    def _render_hints(self) -> dict:
        return {"type": "disabled_button", "message": self.message}


@dataclass
class ActionForm(Eigenform):
    """A button that executes a function with access to sibling state and the store."""
    action_label: str = "Execute"
    action_fn: Callable[[dict, Store, str], dict] | None = None
    depends_on: list[str] = field(default_factory=list)
    precondition_fn: Callable[[dict], bool] | None = None
    precondition_message: str = "Precondition not met."
    confirm: bool = False
    writes_to: list[str] = field(default_factory=list)

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
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        val = data.get("value")
        if isinstance(val, dict):
            status = val.get("status")
            if status == "success":
                result = val.get("result")
                if isinstance(result, dict) and "message" in result:
                    html += f'<p style="color: #2a2;"><strong>Result:</strong> {escape(str(result["message"]))}</p>'
                elif result is not None:
                    html += f'<p style="color: #2a2;"><strong>Result:</strong> {escape(str(result))}</p>'
                else:
                    html += '<p style="color: #2a2;"><strong>Executed successfully.</strong></p>'
            elif status == "error":
                html += f'<p style="color: #c22;"><strong>Error:</strong> {escape(str(val.get("error")))}</p>'
            elif status == "armed":
                html += '<p style="color: #f0a020;"><strong>Armed.</strong> Confirm or cancel.</p>'

        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        action = body.get("action")
        if action == "execute":
            if self.confirm:
                self._store.set(self._scope, self.key, {"status": "armed"})
                return self.serialize()
            return self._execute()
        elif action == "confirm":
            return self._execute()
        elif action == "cancel":
            self._store.set(self._scope, self.key, {"status": "cancelled"})
            return self.serialize()
        result = self.serialize()
        result["error"] = f"Unknown action: {action}"
        result["failed_action"] = action
        return result
