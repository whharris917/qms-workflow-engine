"""BooleanForm — binary yes/no toggle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from typing import Any

from engine.affordances import Affordance
from engine.eigenforms import Eigenform


class ToggleAffordance(Affordance):
    """An affordance showing a yes/no toggle with active state."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 current: bool | None = None,
                 true_label: str = "Yes", false_label: str = "No"):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.current = current
        self.true_label = true_label
        self.false_label = false_label

    def _render_hints(self) -> dict:
        return {
            "type": "toggle",
            "current": self.current,
            "true_label": self.true_label,
            "false_label": self.false_label,
        }


@dataclass
class BooleanForm(Eigenform):
    """Binary yes/no toggle. Distinct from CheckboxForm (multi-select)."""
    true_label: str = "Yes"
    false_label: str = "No"

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "value": self.value,
            "true_label": self.true_label,
            "false_label": self.false_label,
        }

    def get_affordances(self) -> list[Affordance]:
        return [
            ToggleAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": f"<true | false>"},
                instruction=f"Set to true ({self.true_label}) or false ({self.false_label}).",
                current=self.value,
                true_label=self.true_label,
                false_label=self.false_label,
            )
        ]

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        val = data["value"]
        if val is None:
            display = "Not set"
        elif val:
            display = data["true_label"]
        else:
            display = data["false_label"]
        html += f'<p><strong>Value:</strong> {escape(display)}</p>'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        raw = body.get("value")
        if isinstance(raw, bool):
            val = raw
        elif isinstance(raw, str):
            val = raw.lower() in ("true", "yes", "1")
        else:
            val = bool(raw)
        self._store.set(self._scope, self.key, val)
        return self.serialize()
