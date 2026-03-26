"""PageForm — an eigenform that contains and delegates to nested eigenforms."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from pathlib import Path
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

    PageForm is the persistence boundary. Each page owns its own Store
    backed by a separate JSON file (data_dir / "{scope}.json"). Children
    inherit this store via bind().
    """
    eigenforms: list[Eigenform] = field(default_factory=list)

    def bind(self, data_dir: Path, scope: str, url_prefix: str) -> PageForm:
        """Produce a bound copy of this page and all nested eigenforms.

        Unlike other eigenforms, PageForm creates its own Store from
        data_dir rather than receiving one. This makes the page the
        persistence boundary — one JSON file per page.
        """
        import copy
        store = Store(data_dir / f"{scope}.json")
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
                url=self._url_prefix,
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

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h2>{escape(data["label"])}</h2>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        html += "".join(ef.render() for ef in self.eigenforms)
        html += '<div style="margin-top: 12px;">'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        html += '</div>'
        return html

    @staticmethod
    def _get_children(ef: Eigenform) -> list[Eigenform]:
        """Get the direct children of a container eigenform."""
        if hasattr(ef, 'eigenforms'):
            return ef.eigenforms
        if hasattr(ef, 'steps'):
            return ef.steps
        if hasattr(ef, 'tabs'):
            return list(ef.tabs.values())
        return []

    def find_eigenform(self, path: str) -> Eigenform | None:
        """Find an eigenform by its path (e.g., 'tabs/title')."""
        segments = path.split("/")
        children = self.eigenforms
        for segment in segments:
            match = next((ef for ef in children if ef.key == segment), None)
            if match is None:
                return None
            if segment == segments[-1]:
                return match
            children = self._get_children(match)
        return None

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

    def handle_action(self, path: str, body: dict) -> dict | None:
        """Route a POST to the correct nested eigenform by path. Returns full page state."""
        ef = self.find_eigenform(path)
        if ef is None:
            return None
        result = ef.handle(body)
        page_state = self.serialize()
        if "error" in result:
            page_state["error"] = result["error"]
            page_state["failed_action"] = result.get("failed_action")
        return page_state
