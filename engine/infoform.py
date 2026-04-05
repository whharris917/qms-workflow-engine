"""InfoForm — read-only text display with no affordances."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.affordances import Affordance
from engine.eigenform import Eigenform
from engine.templates import render_template


@dataclass
class InfoForm(Eigenform):
    """Display-only text. No interaction, no affordances, always complete.

    text can be a string (rendered as-is) or a dict (rendered as labeled
    key-value pairs in HTML, structured fields in JSON).
    """
    text: str | dict = ""

    @property
    def is_complete(self) -> bool:
        return True

    def _serialize_state(self) -> dict:
        return self._base_state() | {"text": self.text}

    def get_affordances(self) -> list[Affordance]:
        return []

    def render_from_data(self, data: dict) -> str:
        return render_template("info.html", data=data, ef=self)
