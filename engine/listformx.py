"""ListFormX — ListForm reimagined with native HTMX rendering.

This is an experimental copy of ListForm that replaces the affordance-based
rendering pipeline with direct HTMX attributes in the template. The handler
logic is identical — only the rendering path differs.

Two templates:
  - listx.html       — agent view: naked semantic HTMX, no styling
  - listx_human.html — human view: styled layout, same HTMX interactions
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.listform import ListForm
from engine.templates import render_template


@dataclass
class ListFormX(ListForm):
    """HTMX-native ListForm. Same handler logic, HTMX-native rendering."""
    htmx_native = True

    def _template_context(self, data: dict) -> dict:
        """Shared context for both human and agent templates."""
        oc = self._collection
        static_pairs = {(item_id, after_id)
                        for item_id, after_ids in self.must_follow.items()
                        for after_id in after_ids}
        return dict(data=data, ef=self,
                    url=self.url, label=data["label"],
                    instruction=data.get("instruction") or "",
                    items=oc.items,
                    oc=oc,
                    na=data.get("na", False),
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data,
                    allow_constraints=self._effective_allow_constraints,
                    all_must_follow=oc.all_must_follow,
                    id_to_val=oc.id_to_value,
                    static_pairs=static_pairs,
                    stored_constraints=oc.stored_constraints,
                    hints=self._affordance_hints(data))

    def render_from_data(self, data: dict) -> str:
        return render_template("listx_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("listx.html", **self._template_context(data))
