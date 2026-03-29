from __future__ import annotations

from dataclasses import dataclass
from html import escape

from engine.affordances import Affordance, SetValueAffordance
from engine.eigenform import Eigenform


@dataclass
class TextForm(Eigenform):
    """Single free-form string input."""
    default: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.value is not None and self.value != ""

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "value": self.value if self.value is not None else self.default,
        }

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        html += f'<p><strong>Value:</strong> {escape(str(data["value"]))}</p>'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def get_affordances(self) -> list[Affordance]:
        return [
            SetValueAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": "<value>"},
                instruction=f"Replace <value> with the desired {self.label.lower()}.",
            )
        ]

    def _handle(self, body: dict) -> dict:
        self._store.set(self._scope, self.key, body.get("value"))
        return self.serialize()
