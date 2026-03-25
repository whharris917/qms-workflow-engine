"""Eigenform — the self-contained, self-rendering unit of workflow interaction.

An eigenform has internal state, renders itself, and exposes affordances
as POSTable endpoints that mutate its state. Each eigenform is a
HATEOAS-compliant mini-application.

Once bound to a store, scope, and url_prefix, an eigenform is fully
self-sufficient — it can serialize, render, and handle actions
without any external input.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from html import escape
from typing import Any

from engine.affordances import Affordance, SetValueAffordance
from engine.store import Store


@dataclass
class Eigenform:
    """Base protocol for all eigenform types."""
    key: str
    label: str
    instruction: str | None = None

    # Binding — set via bind(), not at construction
    _store: Store | None = None
    _scope: str | None = None
    _url_prefix: str | None = None

    def bind(self, store: Store, scope: str, url_prefix: str) -> Eigenform:
        """Produce a bound copy of this eigenform. The original is unchanged."""
        bound = copy.deepcopy(self)
        bound._store = store
        bound._scope = scope
        bound._url_prefix = url_prefix
        return bound

    @property
    def value(self) -> Any:
        """The current value, fetched from the store."""
        if self._store is None:
            return None
        return self._store.get(self._scope, self.key)

    @property
    def url(self) -> str:
        """The URL for this eigenform's actions."""
        return f"{self._url_prefix}/{self.key}"

    @property
    def uid(self) -> str:
        """Unique DOM ID for this eigenform, scoped to avoid collisions."""
        return f"ef-{self._scope}-{self.key}" if self._scope else f"ef-{self.key}"

    @property
    def form(self) -> str:
        """The eigenform's type name, derived from the class."""
        name = type(self).__name__
        return name.removesuffix("Form").lower()

    def _serialize_state(self) -> dict:
        """Serialize this eigenform's state fields. Subclasses implement this."""
        raise NotImplementedError

    def get_affordances(self) -> list[Affordance]:
        """Produce the affordances available on this eigenform."""
        return []

    def serialize(self) -> dict:
        """Produce the complete canonical representation: state + affordances."""
        state = self._serialize_state()
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def render_inner(self, affordances: list[Affordance]) -> str:
        """Render this eigenform's content as HTML. Subclasses may override."""
        html = f'<h3>{self.label}</h3>'
        if self.instruction:
            html += f'<p>{self.instruction}</p>'
        for aff in affordances:
            html += aff.render()
        return html

    def render(self) -> str:
        """Render this eigenform as HTML, wrapped in a standard container."""
        affordances = self.get_affordances()
        inner = self.render_inner(affordances)

        json_str = escape(json.dumps(self.serialize(), indent=2))
        uid = self.uid

        return (
            f'<div class="eigenform" data-form="{self.form}" data-key="{self.key}"'
            f' style="border: 1px solid #888; padding: 30px 12px 12px 12px; margin: 8px 0; position: relative;">'
            f'<button onclick="var h=document.getElementById(\'{uid}-human\'),j=document.getElementById(\'{uid}-json\'),'
            f'v=j.style.display===\'none\';j.style.display=v?\'block\':\'none\';h.style.display=v?\'none\':\'block\';'
            f'this.textContent=v?\'See HTML\':\'See JSON\'"'
            f' style="position: absolute; top: 8px; right: 8px; font-size: 12px; cursor: pointer; background: #7b2d8b; color: white; border: none; padding: 2px 8px; border-radius: 3px;">See JSON</button>'
            f'<div id="{uid}-human">{inner}</div>'
            f'<pre id="{uid}-json" style="display: none; margin: 0; white-space: pre-wrap;">{json_str}</pre>'
            f'</div>'
        )

    def handle(self, body: dict) -> dict:
        """Handle a POST action. Persists to store, returns serialized state."""
        raise NotImplementedError


@dataclass
class TextForm(Eigenform):
    """Single free-form string input."""
    default: str | None = None

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "value": self.value if self.value is not None else self.default,
        }

    def render_inner(self, affordances: list[Affordance]) -> str:
        display = self.value if self.value is not None else self.default
        html = f'<h3>{self.label}</h3>'
        if self.instruction:
            html += f'<p>{self.instruction}</p>'
        html += f'<p><strong>Value:</strong> {escape(str(display))}</p>'
        for aff in affordances:
            html += aff.render()
        return html

    def get_affordances(self) -> list[Affordance]:
        return [
            SetValueAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                parameters={"value": {"type": "string"}},
            )
        ]

    def handle(self, body: dict) -> dict:
        self._store.set(self._scope, self.key, body.get("value"))
        return self.serialize()
