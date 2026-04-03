"""AccordionFormX — AccordionForm reimagined with native HTMX rendering.

Two templates:
  - accordionx.html       — agent view: naked semantic HTMX, no styling
  - accordionx_human.html — human view: styled layout, same HTMX interactions
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.accordionform import AccordionForm
from engine.templates import render_template


@dataclass
class AccordionFormX(AccordionForm):
    """HTMX-native AccordionForm. Same handler logic, HTMX-native rendering."""
    htmx_native = True

    def _template_context(self, data: dict, agent: bool = False) -> dict:
        """Shared context for both human and agent templates."""
        sections_data = data.get("sections", {})
        section_items = []
        section_html = {}
        for i, sec_key in enumerate(data.get("section_keys", [])):
            ef = self.sections.get(sec_key)
            sec_data = sections_data.get(sec_key, {})
            expanded = sec_data.get("expanded", True) if not data.get("edit_mode") else self._is_expanded(sec_key)
            section_items.append({
                "key": sec_key,
                "label": ef.effective_label if ef else sec_key,
                "expanded": expanded,
                "editable": ef.editable if ef else False,
                "index": i,
            })
            if expanded and ef:
                section_html[sec_key] = ef.render_agent() if agent else ef.render()

        available_types = []
        if data.get("edit_mode"):
            from engine.registry import get_registry
            available_types = sorted(get_registry().available())

        return dict(data=data, ef=self,
                    url=self.url, label=data.get("label", ""),
                    instruction=data.get("instruction") or "",
                    section_items=section_items,
                    section_html=section_html,
                    available_types=available_types,
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data,
                    hints=self._affordance_hints(data))

    def render_from_data(self, data: dict) -> str:
        return render_template("accordionx_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("accordionx.html", **self._template_context(data, agent=True))
