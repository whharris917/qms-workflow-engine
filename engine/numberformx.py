"""NumberFormX — NumberForm reimagined with native HTMX rendering.

Two templates:
  - numberx.html       — agent view: naked semantic HTMX, no styling
  - numberx_human.html — human view: styled layout, same HTMX interactions
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.numberform import NumberForm
from engine.templates import render_template


@dataclass
class NumberFormX(NumberForm):
    """HTMX-native NumberForm. Same handler logic, HTMX-native rendering."""
    htmx_native = True

    def _template_context(self, data: dict) -> dict:
        """Shared context for both human and agent templates."""
        cfg = self._effective_config
        return dict(data=data, ef=self,
                    url=self.url, label=data["label"],
                    instruction=data.get("instruction") or "",
                    value=data.get("value"),
                    min_val=data.get("min"),
                    max_val=data.get("max"),
                    step=data.get("step"),
                    integer=data.get("integer", False),
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data)

    def render_from_data(self, data: dict) -> str:
        return render_template("numberx_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("numberx.html", **self._template_context(data))
