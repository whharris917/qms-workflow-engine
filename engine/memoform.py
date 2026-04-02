"""MemoForm — multi-line text input (textarea)."""

from __future__ import annotations

from dataclasses import dataclass

from engine.affordances import Affordance
from engine.eigenform import Eigenform
from engine.templates import render_template


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
        return render_template("memo.html", data=data, ef=self)

    def _handle(self, body: dict) -> dict:
        val = body.get("value", "")
        if self.min_length is not None and len(val) < self.min_length:
            return self._error(f"Text is too short ({len(val)} chars). Minimum: {self.min_length}", body=body)
        if self.max_length is not None and len(val) > self.max_length:
            return self._error(f"Text is too long ({len(val)} chars). Maximum: {self.max_length}", body=body)
        self._store.set(self._scope, self.key, val)
        return self.serialize()
