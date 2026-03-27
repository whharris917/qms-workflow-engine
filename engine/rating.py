"""RatingForm — ordinal rating selection (1 through N)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance
from engine.eigenforms import Eigenform


class RatingAffordance(Affordance):
    """An affordance for selecting a rating value."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 max_rating: int = 5, current: int | None = None,
                 labels: dict[int, str] | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.max_rating = max_rating
        self.current = current
        self.labels = labels

    def _render_hints(self) -> dict:
        return {
            "type": "rating",
            "max": self.max_rating,
            "current": self.current,
            "labels": self.labels,
        }


@dataclass
class RatingForm(Eigenform):
    """Ordinal rating from 1 to max_rating."""
    max_rating: int = 5
    labels: dict[int, str] | None = None

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
            "max_rating": self.max_rating,
            "labels": self.labels,
        }

    def get_affordances(self) -> list[Affordance]:
        opts = " | ".join(str(i) for i in range(1, self.max_rating + 1))
        return [
            RatingAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": f"<{opts}>"},
                instruction=f"Rate from 1 to {self.max_rating}.",
                max_rating=self.max_rating,
                current=self.value,
                labels=self.labels,
            )
        ]

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        val = data["value"]
        labels = data.get("labels") or {}
        if val is not None:
            label_text = labels.get(str(val), labels.get(val, ""))
            suffix = f" — {escape(str(label_text))}" if label_text else ""
            html += f'<p><strong>Rating:</strong> {val}/{data["max_rating"]}{suffix}</p>'
        else:
            html += '<p style="color: #888;">Not rated.</p>'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        try:
            val = int(body.get("value"))
        except (TypeError, ValueError):
            result = self.serialize()
            result["error"] = f"Invalid rating: {body.get('value')}"
            result["failed_action"] = body
            return result
        if val < 1 or val > self.max_rating:
            result = self.serialize()
            result["error"] = f"Rating must be between 1 and {self.max_rating}, got {val}"
            result["failed_action"] = body
            return result
        self._store.set(self._scope, self.key, val)
        return self.serialize()
