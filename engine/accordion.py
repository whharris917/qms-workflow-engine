"""AccordionForm — collapsible sections, all visible simultaneously.

Unlike TabForm (one-at-a-time), AccordionForm shows all sections with
expand/collapse toggles. Unlike PageForm (always shows everything),
AccordionForm adds collapsibility.

Collapsed sections are omitted from both JSON and HTML — faithful
projection requires the agent and human to see the same information.
The toggle affordances are always present so both can expand any section.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance
from engine.eigenforms import Eigenform
from engine.store import Store


class ToggleSectionAffordance(Affordance):
    """An affordance to expand/collapse an accordion section."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None, expanded: bool = True):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.expanded = expanded

    def _render_hints(self) -> dict:
        return {"type": "accordion_toggle", "expanded": self.expanded}


@dataclass
class AccordionForm(Eigenform):
    """A container with collapsible sections."""
    sections: dict[str, Eigenform] = field(default_factory=dict)

    @property
    def children(self) -> list[Eigenform]:
        return list(self.sections.values())

    @property
    def _expanded_state(self) -> dict[str, bool]:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored
        return {}

    def _is_expanded(self, section_key: str) -> bool:
        return self._expanded_state.get(section_key, True)

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.sections.values())

    def _bind_children(self, store: Store, url_prefix: str):
        self.sections = {
            sec_key: ef.bind(store=store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
            for sec_key, ef in self.sections.items()
        }

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "section_keys": list(self.sections.keys()),
        }

    def serialize(self) -> dict:
        state = self._serialize_state()
        # Only expanded sections include their eigenform — faithful projection.
        # Collapsed sections are absent from both JSON and HTML.
        state["sections"] = {}
        for sec_key, ef in self.sections.items():
            expanded = self._is_expanded(sec_key)
            entry = {"expanded": expanded}
            if expanded:
                entry["eigenform"] = ef.serialize()
            state["sections"][sec_key] = entry
        state["complete"] = self.is_complete
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def get_affordances(self) -> list[Affordance]:
        affordances: list[Affordance] = []
        for sec_key, ef in self.sections.items():
            expanded = self._is_expanded(sec_key)
            affordances.append(ToggleSectionAffordance(
                label=ef.label,
                method="POST",
                url=f"{self._url_prefix}/{self.key}",
                body={"action": "toggle", "section": sec_key},
                instruction=f"{'Collapse' if expanded else 'Expand'} the {ef.label} section.",
                expanded=expanded,
            ))
        return affordances

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        sections = data.get("sections", {})
        affs = data.get("affordances", [])

        for sec_key in data.get("section_keys", []):
            sec_data = sections.get(sec_key, {})
            expanded = sec_data.get("expanded", True)

            # Render toggle header
            for aff in affs:
                if aff.get("body", {}).get("section") == sec_key:
                    html += render_affordance_html(aff)
                    break

            # Render section content if expanded
            if expanded:
                ef = self.sections.get(sec_key)
                if ef:
                    html += f'<div style="padding-left: 12px; border-left: 2px solid #ddd; margin-bottom: 8px;">'
                    html += ef.render()
                    html += '</div>'

        return html

    def _handle(self, body: dict) -> dict:
        if body.get("action") == "toggle":
            sec_key = body.get("section")
            if sec_key in self.sections:
                state = dict(self._expanded_state)
                state[sec_key] = not self._is_expanded(sec_key)
                self._store.set(self._scope, self.key, state)
        return self.serialize()

    def handle_action(self, key: str, body: dict) -> bool:
        """Route action: toggle goes to self, otherwise search all sections."""
        if key == self.key:
            self.handle(body)
            return True
        for ef in self.sections.values():
            if ef.key == key:
                ef.handle(body)
                return True
            if hasattr(ef, 'handle_action') and ef.handle_action(key, body):
                return True
        return False
