"""MemoFormX — MemoForm reimagined with native HTMX rendering.

Two templates:
  - memox.html       — agent view: naked semantic HTMX, no styling
  - memox_human.html — human view: styled layout, same HTMX interactions
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.memoform import MemoForm
from engine.templates import render_template


@dataclass
class MemoFormX(MemoForm):
    """HTMX-native MemoForm. Same handler logic, HTMX-native rendering."""
    htmx_native = True

    def _template_context(self, data: dict) -> dict:
        """Shared context for both human and agent templates."""
        return dict(data=data, ef=self,
                    url=self.url, label=data["label"],
                    instruction=data.get("instruction") or "",
                    value=data.get("value"),
                    min_length=data.get("min_length"),
                    max_length=data.get("max_length"),
                    placeholder=self.placeholder or "",
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data)

    def render_from_data(self, data: dict) -> str:
        return render_template("memox_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("memox.html", **self._template_context(data))
