"""ChoiceFormX — ChoiceForm reimagined with native HTMX rendering.

Two templates:
  - choicex.html       — agent view: naked semantic HTMX, no styling
  - choicex_human.html — human view: styled layout, same HTMX interactions
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.choiceform import ChoiceForm
from engine.templates import render_template


@dataclass
class ChoiceFormX(ChoiceForm):
    """HTMX-native ChoiceForm. Same handler logic, HTMX-native rendering."""
    htmx_native = True

    def _template_context(self, data: dict) -> dict:
        """Shared context for both human and agent templates."""
        options_html = self._options_form.render() if data.get("edit_mode") else ""
        return dict(data=data, ef=self,
                    url=self.url, label=data["label"],
                    instruction=data.get("instruction") or "",
                    value=data.get("value"),
                    options=data.get("options", []),
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data,
                    options_html=options_html)

    def render_from_data(self, data: dict) -> str:
        return render_template("choicex_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("choicex.html", **self._template_context(data))
