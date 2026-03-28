"""DynamicChoiceForm — a choice whose options depend on a sibling's value.

Like ChoiceForm, but options are computed dynamically from a dependency
rather than fixed at definition time. Supports both a callable
(options_fn) and a lookup table (static_options).

When the dependency changes and the currently selected value is no longer
valid, the selection is marked "stale" rather than silently cleared.
The user must explicitly re-select or clear.

ORDERING: The dependency must appear before DynamicChoiceForm in the
parent's children list, since options are computed from the live store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any, Callable

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.choice import SelectAffordance
from engine.eigenforms import Eigenform


@dataclass
class DynamicChoiceForm(Eigenform):
    """Single selection from a dynamically computed set of options."""
    depends_on: str = ""
    options_fn: Callable[[Any], list[str]] | None = None
    static_options: dict[Any, list[str]] | None = None

    @property
    def _dep_value(self):
        if self._store is None:
            return None
        return self._store.get(self._scope, self.depends_on)

    @property
    def current_options(self) -> list[str]:
        dep = self._dep_value
        if dep is None:
            return []
        if self.options_fn is not None:
            return self.options_fn(dep) or []
        if self.static_options is not None:
            return self.static_options.get(dep, [])
        return []

    @property
    def stale(self) -> bool:
        return self.value is not None and self.value not in self.current_options

    @property
    def is_complete(self) -> bool:
        return self.value is not None and self.value in self.current_options

    def _serialize_state(self) -> dict:
        state = {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "value": self.value,
            "options": self.current_options,
            "depends_on": self.depends_on,
        }
        if self.stale:
            state["stale"] = True
        return state

    def get_affordances(self) -> list[Affordance]:
        options = self.current_options
        affs: list[Affordance] = []

        if not options:
            return []

        opts = " | ".join(options)
        affs.append(SelectAffordance(
            label=f"Set {self.label}",
            method="POST",
            url=self.url,
            body={"value": f"<{opts}>"},
            instruction=f"Select one of: {opts}.",
            options=options,
            current=self.value if not self.stale else None,
        ))

        if self.stale:
            affs.append(SimpleButtonAffordance(
                label="Clear Selection",
                method="POST",
                url=self.url,
                body={"action": "clear"},
                instruction="Clear the stale selection.",
            ))

        return affs

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        if not data.get("options"):
            html += '<p style="color: #888;"><em>Waiting for dependency to be set.</em></p>'
        else:
            val = data.get("value")
            if data.get("stale"):
                html += (
                    f'<p style="color: #c22;"><strong>Stale selection:</strong> '
                    f'"{escape(str(val))}" is no longer a valid option. Please re-select.</p>'
                )
            else:
                html += f'<p><strong>Selected:</strong> {escape(str(val or "None"))}</p>'

        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        action = body.get("action")
        if action == "clear":
            self._store.set(self._scope, self.key, None)
            return self.serialize()

        value = body.get("value")
        if value in self.current_options:
            self._store.set(self._scope, self.key, value)
        else:
            result = self.serialize()
            result["error"] = f"'{value}' is not a valid option."
            result["failed_action"] = "set"
            return result
        return self.serialize()
