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

    def render_html(self) -> str:
        endpoint = f'{self.method} {self.url}'
        html = '<div style="margin: 4px 0;">'
        for opt in self.options:
            checked = " checked" if opt == self.current else ""
            body_js = json.dumps({"value": opt}).replace('"', '&quot;')
            html += (
                f'<label style="display: block; cursor: pointer; padding: 2px 0;">'
                f'<input type="radio" name="{escape(self.url)}"{checked} onchange="'
                f"fetch('{self.url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                f"body:JSON.stringify({{value:'{escape(opt)}'}})}}).then(()=>location.reload())"
                f'" title="{escape(endpoint)} {escape(json.dumps({"value": opt}))}"'
                f' /> {escape(opt)}'
                f'</label>'
            )
        html += '</div>'
        return html


@dataclass
class ChoiceForm(Eigenform):
    """Single selection from a fixed set of options."""
    options: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.value is not None and self.value in self.options

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
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

    def render_inner(self, affordances: list[Affordance]) -> str:
        html = f'<h3>{self.label}</h3>'
        if self.instruction:
            html += f'<p>{self.instruction}</p>'
        html += f'<p><strong>Selected:</strong> {escape(str(self.value or "None"))}</p>'
        for aff in affordances:
            html += aff.render()
        return html

    def handle(self, body: dict) -> dict:
        value = body.get("value")
        if value in self.options:
            self._store.set(self._scope, self.key, value)
        return self.serialize()
