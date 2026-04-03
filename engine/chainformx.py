"""ChainFormX — ChainForm reimagined with native HTMX rendering.

Two templates:
  - chainx.html       — agent view: naked semantic HTMX, no styling
  - chainx_human.html — human view: styled layout, same HTMX interactions
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.chainform import ChainForm
from engine.templates import render_template


@dataclass
class ChainFormX(ChainForm):
    """HTMX-native ChainForm. Same handler logic, HTMX-native rendering."""
    htmx_native = True

    def _template_context(self, data: dict, agent: bool = False) -> dict:
        """Shared context for both human and agent templates."""
        active_key = data.get("active_step")
        step_items = []
        for i, ef in enumerate(self.steps):
            step_items.append({
                "key": ef.key,
                "label": ef.effective_label,
                "is_active": ef.key == active_key,
                "editable": ef.editable,
                "index": i,
                "complete": ef.is_complete,
            })
        active = self.active_step
        active_html = (active.render_agent() if agent else active.render()) if active else ""

        available_types = []
        if data.get("edit_mode"):
            from engine.registry import get_registry
            available_types = sorted(get_registry().available())

        return dict(data=data, ef=self,
                    url=self.url, label=data.get("label", ""),
                    instruction=data.get("instruction") or "",
                    active_step_key=active_key,
                    step_items=step_items,
                    active_html=active_html,
                    available_types=available_types,
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data,
                    hints=self._affordance_hints(data))

    def render_from_data(self, data: dict) -> str:
        return render_template("chainx_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("chainx.html", **self._template_context(data, agent=True))
