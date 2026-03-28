"""NumberForm — numeric input with min/max bounds, step, and optional integer constraint."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from typing import Any

from engine.affordances import Affordance
from engine.eigenforms import Eigenform


class NumberInputAffordance(Affordance):
    """An affordance for numeric input with validation hints."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 min_val: float | None = None, max_val: float | None = None,
                 step: float | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.min_val = min_val
        self.max_val = max_val
        self.step = step

    def _render_hints(self) -> dict:
        return {"type": "number_input", "min": self.min_val, "max": self.max_val, "step": self.step}


@dataclass
class NumberForm(Eigenform):
    """Numeric input with optional bounds and step."""
    min_val: float | None = None
    max_val: float | None = None
    step: float | None = None
    integer: bool = False

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
            "min": self.min_val,
            "max": self.max_val,
            "step": self.step,
            "integer": self.integer,
        }

    def get_affordances(self) -> list[Affordance]:
        parts = []
        if self.min_val is not None:
            parts.append(f"min {self.min_val}")
        if self.max_val is not None:
            parts.append(f"max {self.max_val}")
        hint = f" ({', '.join(parts)})" if parts else ""
        return [
            NumberInputAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": "<number>"},
                instruction=f"Enter a number{hint}.",
                min_val=self.min_val,
                max_val=self.max_val,
                step=self.step,
            )
        ]

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        # Constraints summary
        constraints = []
        if data.get("min") is not None:
            constraints.append(f'min: {data["min"]}')
        if data.get("max") is not None:
            constraints.append(f'max: {data["max"]}')
        if data.get("step") is not None:
            constraints.append(f'step: {data["step"]}')
        if data.get("integer"):
            constraints.append("integer")
        if constraints:
            html += (
                f'<p style="color: #666; font-size: 0.9em; margin: 2px 0;">'
                f'{escape(", ".join(constraints))}</p>'
            )

        val = data["value"]
        html += f'<p><strong>Value:</strong> {escape(str(val if val is not None else "None"))}</p>'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        raw = body.get("value")
        try:
            val = int(raw) if self.integer else float(raw)
        except (TypeError, ValueError):
            result = self.serialize()
            result["error"] = f"Invalid number: {raw}"
            result["failed_action"] = body
            return result
        if self.min_val is not None and val < self.min_val:
            result = self.serialize()
            result["error"] = f"Value {val} is below minimum {self.min_val}"
            result["failed_action"] = body
            return result
        if self.max_val is not None and val > self.max_val:
            result = self.serialize()
            result["error"] = f"Value {val} is above maximum {self.max_val}"
            result["failed_action"] = body
            return result
        if self.step is not None:
            base = self.min_val if self.min_val is not None else 0
            remainder = abs((val - base) % self.step)
            if min(remainder, self.step - remainder) > 1e-9:
                result = self.serialize()
                result["error"] = f"Value {val} is not a valid step (step {self.step} from {base})"
                result["failed_action"] = body
                return result
        self._store.set(self._scope, self.key, val)
        return self.serialize()
