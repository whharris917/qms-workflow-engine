"""VisibilityForm — an eigenform whose visibility depends on another eigenform's value."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.eigenforms import Eigenform
from engine.store import Store


@dataclass
class VisibilityForm(Eigenform):
    """Wraps an eigenform with a visibility condition.

    The wrapped eigenform is only visible (serialized, rendered, and
    required for completion) when the depended-on sibling eigenform
    has a matching value. When invisible, this form is complete by
    default and absent from the HTML.
    """
    eigenform: Eigenform = None
    depends_on: str = ""
    visible_when: Any = None  # single value or list of values

    @property
    def children(self) -> list:
        return [self.eigenform] if self.eigenform else []

    @property
    def _dep_value(self):
        """The current value of the depended-on eigenform."""
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
        return self.eigenform.is_complete

    def _bind_children(self, store: Store, url_prefix: str):
        self.eigenform = self.eigenform.bind(
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

    def serialize(self) -> dict | None:
        if not self.visible:
            return None
        state = self._serialize_state()
        state["complete"] = self.is_complete
        state["eigenform"] = self.eigenform.serialize()
        state["affordances"] = []
        return state

    def render(self) -> str:
        if not self.visible:
            return ""
        return self.eigenform.render()

    def render_from_data(self, data: dict) -> str:
        return self.eigenform.render()

    def handle(self, body: dict) -> dict:
        if self.visible:
            return self.eigenform.handle(body)
        return self.serialize()

    def _handle(self, body: dict) -> dict:
        return self.handle(body)
