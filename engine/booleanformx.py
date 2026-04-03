"""BooleanFormX — BooleanForm reimagined with native HTMX rendering.

Two templates:
  - booleanx.html       — agent view: naked semantic HTMX, no styling
  - booleanx_human.html — human view: styled layout, same HTMX interactions
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.booleanform import BooleanForm
from engine.templates import render_template


@dataclass
class BooleanFormX(BooleanForm):
    """HTMX-native BooleanForm. Same handler logic, HTMX-native rendering."""
    htmx_native = True

    def _template_context(self, data: dict) -> dict:
        """Shared context for both human and agent templates."""
        return dict(data=data, ef=self,
                    url=self.url, label=data["label"],
                    instruction=data.get("instruction") or "",
                    value=data.get("value"),
                    true_label=data.get("true_label", "Yes"),
                    false_label=data.get("false_label", "No"),
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data,
                    hints=self._affordance_hints(data))

    def render_from_data(self, data: dict) -> str:
        return render_template("booleanx_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("booleanx.html", **self._template_context(data))
