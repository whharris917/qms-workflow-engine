"""MemoForm — multi-line text input (textarea)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from typing import Any

from engine.affordances import Affordance
from engine.eigenform import Eigenform


class MemoAffordance(Affordance):
    """An affordance for multi-line text input."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 max_length: int | None = None, min_length: int | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.max_length = max_length
        self.min_length = min_length

    def _render_hints(self) -> dict:
        return {"type": "textarea", "max_length": self.max_length, "min_length": self.min_length}


@dataclass
class MemoForm(Eigenform):
    """Multi-line text input. TextForm is single-line; MemoForm handles paragraphs."""
    max_length: int | None = None
    min_length: int | None = None
    placeholder: str | None = None

    @property
    def is_complete(self) -> bool:
        val = self.value
        if val is None or len(val.strip()) == 0:
            return False
        if self.min_length is not None and len(val) < self.min_length:
            return False
        return True

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "value": self.value,
            "min_length": self.min_length,
            "max_length": self.max_length,
        }

    def get_affordances(self) -> list[Affordance]:
        parts = []
        if self.min_length:
            parts.append(f"min {self.min_length} chars")
        if self.max_length:
            parts.append(f"max {self.max_length} chars")
        hint = f" ({', '.join(parts)})" if parts else ""
        return [
            MemoAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": "<text>"},
                instruction=f"Enter multi-line text{hint}.",
                max_length=self.max_length,
                min_length=self.min_length,
            )
        ]

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        val = data["value"]
        if val:
            html += f'<div style="white-space: pre-wrap; background: #f5f5f5; padding: 8px; margin: 4px 0; border-radius: 4px;">{escape(val)}</div>'
        else:
            html += '<p style="color: #888;">No text entered.</p>'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        val = body.get("value", "")
        if self.min_length is not None and len(val) < self.min_length:
            return self._error(f"Text is too short ({len(val)} chars). Minimum: {self.min_length}", body=body)
        if self.max_length is not None and len(val) > self.max_length:
            return self._error(f"Text is too long ({len(val)} chars). Maximum: {self.max_length}", body=body)
        self._store.set(self._scope, self.key, val)
        return self.serialize()
