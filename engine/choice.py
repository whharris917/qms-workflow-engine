"""ChoiceForm — single selection from a list of options."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance
from engine.eigenforms import Eigenform


class SelectAffordance(Affordance):
    """An affordance that selects one option from a list."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None, options: list[str] | None = None,
                 current: str | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.options = options or []
        self.current = current

    def _render_hints(self) -> dict:
        return {"type": "radio", "options": self.options, "current": self.current}


@dataclass
class ChoiceForm(Eigenform):
    """Single selection from a fixed set of options."""
    options: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.value is not None and self.value in self.options

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "value": self.value,
            "options": self.options,
        }

    def get_affordances(self) -> list[Affordance]:
        opts = " | ".join(self.options)
        return [
            SelectAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": f"<{opts}>"},
                instruction=f"Select one of: {opts}.",
                options=self.options,
                current=self.value,
            )
        ]

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        html += f'<p><strong>Selected:</strong> {escape(str(data["value"] or "None"))}</p>'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        value = body.get("value")
        if value in self.options:
            self._store.set(self._scope, self.key, value)
        return self.serialize()
