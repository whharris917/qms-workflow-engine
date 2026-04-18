"""Switch — selects between named alternatives based on a sibling's value."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.component import Component, render_dependency_line
from engine.sibling_ref import SiblingRef
from engine.templates import render_template
from engine.store import Store


@dataclass
class Switch(Component):
    """Container that swaps between pre-defined component subtrees
    based on a sibling component's current value.

    Like Visibility but for N-way selection rather than show/hide.
    Only the active case is serialized and rendered (faithful projection).
    Previously-visited cases preserve their state in the store.

    If the dependency value doesn't match any case key, nothing is active
    and the Switch serializes as empty / renders as a placeholder.
    """
    form = "switch"

    depends_on: "str | SiblingRef" = ""
    cases: dict[str, Component] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        if self.depends_on:
            self.depends_on = SiblingRef.coerce(self.depends_on)

    def _sibling_refs(self) -> list[SiblingRef]:
        return [self.depends_on] if isinstance(self.depends_on, SiblingRef) else []

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["cases"] = {k: v.to_descriptor() for k, v in self.cases.items()}
        return desc

    @property
    def children(self) -> list[Component]:
        return list(self.cases.values())

    @property
    def _dep_value(self):
        """The current value of the depended-on sibling component."""
        if self._store is None:
            return None
        return self._store.get(self._scope, self.depends_on)

    @property
    def active_case_key(self) -> str | None:
        """The case key matching the dependency value, or None."""
        val = self._dep_value
        if val is not None and val in self.cases:
            return val
        return None

    @property
    def active_case(self) -> Component | None:
        key = self.active_case_key
        if key is None:
            return None
        return self.cases[key]

    @property
    def is_complete(self) -> bool:
        active = self.active_case
        if active is None:
            return True
        return active.is_complete

    def _bind_children(self, store: Store, url_prefix: str):
        self.cases = {
            case_key: ef.bind(
                store=store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}",
            )
            for case_key, ef in self.cases.items()
        }

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "depends_on": self.depends_on,
            "active_case": self.active_case_key,
            "case_keys": list(self.cases.keys()),
        }

    def _serialize_full(self) -> dict:
        state = self._serialize_state()
        active = self.active_case
        state["component"] = active.serialize() if active else None
        state["complete"] = self.is_complete
        state["affordances"] = []
        return state

    def render_from_data(self, data: dict) -> str:
        active = self.active_case
        active_html = active.render_safely() if active else None
        dep_line = render_dependency_line(data.get("depends_on"), self._url_prefix)
        return render_template("switch.html", data=data, ef=self, url_prefix=self._url_prefix, active_html=active_html, dep_line=dep_line, case_keys=data.get("case_keys", []), depends_on=data.get("depends_on", ""))

    def _handle(self, body: dict) -> dict:
        active = self.active_case
        if active:
            return active.handle(body)
        return self.serialize()
