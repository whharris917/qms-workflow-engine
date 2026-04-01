"""RangeForm — slider over a continuous range."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from typing import Any

from engine.affordances import Affordance
from engine.eigenform import Eigenform


class RangeAffordance(Affordance):
    """An affordance for range/slider input."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 min_val: float = 0, max_val: float = 100,
                 step: float = 1, current: float | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.current = current

    def _render_hints(self) -> dict:
        return {
            "type": "range_input",
            "min": self.min_val,
            "max": self.max_val,
            "step": self.step,
            "current": self.current,
        }


@dataclass
class RangeForm(Eigenform):
    """Select a numeric value from a continuous range via slider."""
    min_val: float = 0
    max_val: float = 100
    step: float = 1
    unit: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "value": self.value,
            "min": self.min_val,
            "max": self.max_val,
            "step": self.step,
            "unit": self.unit,
        }

    def get_affordances(self) -> list[Affordance]:
        return [
            RangeAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": f"<{self.min_val}..{self.max_val}>"},
                instruction=f"Set a value between {self.min_val} and {self.max_val} (step {self.step}).",
                min_val=self.min_val,
                max_val=self.max_val,
                step=self.step,
                current=self.value,
            )
        ]

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        val = data["value"]
        unit = data.get("unit") or ""
        if val is not None:
            html += f'<p><strong>Value:</strong> {val}{escape(unit)}</p>'
        else:
            html += '<p style="color: #888;">Not set.</p>'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        try:
            val = float(body.get("value"))
        except (TypeError, ValueError):
            return self._error(f"Invalid number: {body.get('value')}", body=body)
        if val < self.min_val:
            return self._error(f"Value {val} is below minimum {self.min_val}", body=body)
        if val > self.max_val:
            return self._error(f"Value {val} is above maximum {self.max_val}", body=body)
        self._store.set(self._scope, self.key, val)
        return self.serialize()
