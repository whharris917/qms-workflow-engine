"""CheckboxFormX — CheckboxForm reimagined with native HTMX rendering.

Two templates:
  - checkboxx.html       — agent view: naked semantic HTMX, no styling
  - checkboxx_human.html — human view: styled layout, same HTMX interactions
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.checkboxform import CheckboxForm
from engine.templates import render_template


@dataclass
class CheckboxFormX(CheckboxForm):
    """HTMX-native CheckboxForm. Same handler logic, HTMX-native rendering."""
    htmx_native = True

    def _template_context(self, data: dict) -> dict:
        """Shared context for both human and agent templates."""
        items_html = self._items_form.render() if data.get("edit_mode") else ""
        return dict(data=data, ef=self,
                    url=self.url, label=data["label"],
                    instruction=data.get("instruction") or "",
                    items=data.get("items", {}),
                    confirmed=data.get("confirmed", False),
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data,
                    items_html=items_html,
                    hints=self._affordance_hints(data))

    def render_from_data(self, data: dict) -> str:
        return render_template("checkboxx_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("checkboxx.html", **self._template_context(data))
