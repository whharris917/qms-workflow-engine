"""PageForm — an eigenform that contains and delegates to nested eigenforms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.affordances import Affordance, SimpleButtonAffordance
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

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.eigenforms)

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
        }

    def get_affordances(self) -> list[Affordance]:
        return [
            SimpleButtonAffordance(
                label="Reset Page",
                method="POST",
                url=f"{self._url_prefix}/{self.key}",
                body={"action": "reset"},
                instruction="Clear all state on this page.",
            )
        ]

    def serialize(self) -> dict:
        state = self._serialize_state()
        state["eigenforms"] = [ef.serialize() for ef in self.eigenforms]
        state["complete"] = self.is_complete
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def render_inner(self, affordances: list[Affordance]) -> str:
        html = f'<h2>{self.label}</h2>'
        if self.instruction:
            html += f'<p>{self.instruction}</p>'
        html += "".join(ef.render() for ef in self.eigenforms)
        html += '<div style="margin-top: 12px;">'
        for aff in affordances:
            html += aff.render()
        html += '</div>'
        return html

    def _clear_recursive(self, eigenforms: list[Eigenform]):
        """Clear state for all eigenforms, recursing into containers."""
        for ef in eigenforms:
            if ef._scope:
                self._store.clear_scope(ef._scope)
            if hasattr(ef, 'eigenforms'):
                self._clear_recursive(ef.eigenforms)
            if hasattr(ef, 'steps'):
                self._clear_recursive(ef.steps)
            if hasattr(ef, 'tabs'):
                self._clear_recursive(list(ef.tabs.values()))

    def handle(self, body: dict) -> dict:
        """Handle page-level actions."""
        if body.get("action") == "reset":
            self._store.clear_scope(self._scope)
            self._clear_recursive(self.eigenforms)
        return self.serialize()

    def handle_action(self, key: str, body: dict) -> dict | None:
        """Route a POST to the correct nested eigenform. Returns full page state."""
        # Page-level action
        if key == self.key:
            self.handle(body)
            return self.serialize()
        for ef in self.eigenforms:
            # Direct match
            if ef.key == key:
                result = ef.handle(body)
                page_state = self.serialize()
                if "error" in result:
                    page_state["error"] = result["error"]
                    page_state["failed_action"] = result.get("failed_action")
                return page_state
            # Delegate to containers that can route internally
            if hasattr(ef, 'handle_action'):
                if ef.handle_action(key, body):
                    return self.serialize()
        return None
