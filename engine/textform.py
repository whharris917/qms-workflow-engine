from __future__ import annotations

from dataclasses import dataclass

from engine.affordances import Affordance, SetValueAffordance
from engine.eigenform import Eigenform
from engine.templates import render_template


@dataclass
class TextForm(Eigenform):
    """Single free-form string input."""
    htmx_native = True
    default: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.value is not None and self.value != ""

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "value": self.value if self.value is not None else self.default,
        }

    def _template_context(self, data: dict) -> dict:
        return dict(data=data, ef=self,
                    url=self.url, label=data["label"],
                    instruction=data.get("instruction") or "",
                    value=data.get("value"),
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data,
                    undo_depth=self._undo_depth if self.edit_mode else 0,
                    hints=self._affordance_hints(data))

    def render_from_data(self, data: dict) -> str:
        return render_template("text_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("text.html", **self._template_context(data))

    def get_affordances(self) -> list[Affordance]:
        return [
            SetValueAffordance(
                label=f"Set {self.effective_label}",
                method="POST",
                url=self.url,
                body={"value": "<value>"},
                instruction=f"Replace <value> with the desired {self.effective_label.lower()}.",
            )
        ]

    def _handle(self, body: dict) -> dict:
        self._store.set(self._scope, self.key, body.get("value"))
        return self.serialize()
