"""Visibility — a component whose visibility depends on another component's value."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from engine.component import Component
from engine.sibling_ref import SiblingRef
from engine.templates import render_template
from engine.store import Store


@dataclass
class Visibility(Component):
    """Wraps a component with a visibility condition.

    The wrapped component is only visible (serialized, rendered, and
    required for completion) when the depended-on sibling component
    has a matching value. When invisible, this form is complete by
    default and absent from the HTML.
    """
    form = "visibility"

    component: Component = None
    depends_on: "str | SiblingRef" = ""
    visible_when: Any = None  # single value or list of values

    def __post_init__(self):
        if self.depends_on:
            self.depends_on = SiblingRef.coerce(self.depends_on)

    def _sibling_refs(self) -> list[SiblingRef]:
        return [self.depends_on] if isinstance(self.depends_on, SiblingRef) else []

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        if self.component:
            desc["component"] = self.component.to_descriptor()
        return desc

    @property
    def children(self) -> list:
        return [self.component] if self.component else []

    @property
    def _dep_value(self):
        """The current value of the depended-on component."""
        if self._store is None:
            return None
        return self._store.get(self._scope, self.depends_on)

    @property
    def visible(self) -> bool:
        val = self._dep_value
        if callable(self.visible_when):
            return self.visible_when(val)
        if isinstance(self.visible_when, list):
            return val in self.visible_when
        return val == self.visible_when

    @property
    def is_complete(self) -> bool:
        if not self.visible:
            return True
        return self.component.is_complete

    def _bind_children(self, store: Store, url_prefix: str):
        self.component = self.component.bind(
            store=store, scope=self._scope, url_prefix=f"{url_prefix}/{self.key}",
        )

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "depends_on": self.depends_on,
            "visible": self.visible,
        }

    def _serialize_full(self) -> dict | None:
        if not self.visible:
            return None
        state = self._serialize_state()
        state["complete"] = self.is_complete
        state["component"] = self.component.serialize()
        state["affordances"] = []
        return state

    def render(self) -> str:
        if not self.visible:
            return ""
        return self.component.render_safely()

    def render_from_data(self, data: dict) -> str:
        return render_template("visibility.html", child_html=self.component.render_safely())

    def handle(self, body: dict) -> dict:
        if self.visible:
            return self.component.handle(body)
        return self.serialize()

    def _handle(self, body: dict) -> dict:
        return self.handle(body)
