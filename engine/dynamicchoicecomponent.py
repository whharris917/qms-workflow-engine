"""DynamicChoiceComponent — a choice whose options depend on a sibling's value.

Like ChoiceComponent, but options are computed dynamically from a dependency
rather than fixed at definition time. Supports both a callable
(options_fn) and a lookup table (static_options).

When the dependency changes and the currently selected value is no longer
valid, the selection is marked "stale" rather than silently cleared.
The user must explicitly re-select or clear.

ORDERING: The dependency must appear before DynamicChoiceComponent in the
parent's children list, since options are computed from the live store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.choicecomponent import SelectAffordance
from engine.component import Component
from engine.sibling_ref import SiblingRef
from engine.templates import render_template


@dataclass
class DynamicChoiceComponent(Component):
    """Single selection from a dynamically computed set of options."""
    depends_on: "str | SiblingRef" = ""
    options_fn: Callable[[Any], list[str]] | None = None
    static_options: dict[Any, list[str]] | None = None

    def __post_init__(self):
        if self.depends_on:
            self.depends_on = SiblingRef.coerce(self.depends_on)

    def _sibling_refs(self) -> list[SiblingRef]:
        return [self.depends_on] if isinstance(self.depends_on, SiblingRef) else []

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
        state = self._base_state() | {
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
        return render_template("dynamicchoice.html", data=data, ef=self,
                               url_prefix=self._url_prefix)

    def _handle(self, body: dict) -> dict:
        action = body.get("action")
        if action == "clear":
            self._store.set(self._scope, self.key, None)
            return self.serialize()

        value = body.get("value")
        if value in self.current_options:
            self._store.set(self._scope, self.key, value)
        else:
            return self._error(f"'{value}' is not a valid option.", body=body)
        return self.serialize()
