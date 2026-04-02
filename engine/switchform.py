"""SwitchForm — selects between named alternatives based on a sibling's value."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.eigenform import Eigenform, render_dependency_line
from engine.templates import render_template
from engine.store import Store


@dataclass
class SwitchForm(Eigenform):
    """Container that swaps between pre-defined eigenform subtrees
    based on a sibling eigenform's current value.

    Like VisibilityForm but for N-way selection rather than show/hide.
    Only the active case is serialized and rendered (faithful projection).
    Previously-visited cases preserve their state in the store.

    If the dependency value doesn't match any case key, nothing is active
    and the SwitchForm serializes as empty / renders as a placeholder.
    """
    depends_on: str = ""
    cases: dict[str, Eigenform] = field(default_factory=dict)

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["cases"] = {k: v.to_descriptor() for k, v in self.cases.items()}
        return desc

    @property
    def children(self) -> list[Eigenform]:
        return list(self.cases.values())

    @property
    def _dep_value(self):
        """The current value of the depended-on sibling eigenform."""
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
    def active_case(self) -> Eigenform | None:
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
        state["eigenform"] = active.serialize() if active else None
        state["complete"] = self.is_complete
        state["affordances"] = []
        return state

    def render_from_data(self, data: dict) -> str:
        active = self.active_case
        active_html = active.render() if active else None
        dep_line = render_dependency_line(data.get("depends_on"), self._url_prefix)
        return render_template("switch.html", data=data, ef=self, url_prefix=self._url_prefix, active_html=active_html, dep_line=dep_line, case_keys=data.get("case_keys", []), depends_on=data.get("depends_on", ""))

    def _handle(self, body: dict) -> dict:
        active = self.active_case
        if active:
            return active.handle(body)
        return self.serialize()
