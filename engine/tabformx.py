"""TabFormX — TabForm reimagined with native HTMX rendering.

Two templates:
  - tabx.html       — agent view: naked semantic HTMX, no styling
  - tabx_human.html — human view: styled layout, same HTMX interactions
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.tabform import TabForm
from engine.templates import render_template


@dataclass
class TabFormX(TabForm):
    """HTMX-native TabForm. Same handler logic, HTMX-native rendering."""
    htmx_native = True

    def _template_context(self, data: dict, agent: bool = False) -> dict:
        """Shared context for both human and agent templates."""
        active_key = data.get("active_tab", "")
        tab_items = []
        for i, tab_key in enumerate(data.get("tab_keys", [])):
            ef = self.tabs.get(tab_key)
            tab_items.append({
                "key": tab_key,
                "label": ef.effective_label if ef else tab_key,
                "is_active": tab_key == active_key,
                "editable": ef.editable if ef else False,
                "index": i,
            })
        active = self.active_tab
        active_html = (active.render_agent() if agent else active.render()) if active else ""

        available_types = []
        if data.get("edit_mode"):
            from engine.registry import get_registry
            available_types = sorted(get_registry().available())

        return dict(data=data, ef=self,
                    url=self.url, label=data.get("label", ""),
                    instruction=data.get("instruction") or "",
                    active_tab_key=active_key,
                    tab_items=tab_items,
                    active_html=active_html,
                    available_types=available_types,
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data)

    def render_from_data(self, data: dict) -> str:
        return render_template("tabx_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("tabx.html", **self._template_context(data, agent=True))
