"""PageForm — an eigenform that contains and delegates to nested eigenforms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.affordances import Affordance
from engine.eigenforms import Eigenform
from engine.store import Store


@dataclass
class PageForm(Eigenform):
    """An eigenform whose content is other eigenforms.

    PageForm is responsible for rendering itself, but it delegates rendering
    of its nested eigenforms to the eigenforms themselves. It provides each
    nested eigenform a region and lets them fill it.
    """
    eigenforms: list[Eigenform] = field(default_factory=list)

    def bind(self, store: Store, scope: str, url_prefix: str) -> PageForm:
        """Produce a bound copy of this page and all nested eigenforms."""
        import copy
        bound = copy.deepcopy(self)
        bound._store = store
        bound._scope = scope
        bound._url_prefix = url_prefix
        bound.eigenforms = [
            ef.bind(store=store, scope=bound.key, url_prefix=url_prefix)
            for ef in self.eigenforms
        ]
        return bound

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
        }

    def serialize(self) -> dict:
        state = self._serialize_state()
        state["eigenforms"] = [ef.serialize() for ef in self.eigenforms]
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def render_inner(self, affordances: list[Affordance]) -> str:
        html = f'<h2>{self.label}</h2>'
        if self.instruction:
            html += f'<p>{self.instruction}</p>'
        html += "".join(ef.render() for ef in self.eigenforms)
        return html

    def handle_action(self, key: str, body: dict) -> dict | None:
        """Route a POST to the correct nested eigenform. Returns full page state."""
        for ef in self.eigenforms:
            # Direct match
            if ef.key == key:
                ef.handle(body)
                return self.serialize()
            # Delegate to containers that can route internally
            if hasattr(ef, 'handle_action'):
                if ef.handle_action(key, body):
                    return self.serialize()
        return None
