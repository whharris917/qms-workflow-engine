"""SequenceForm — a gated sequence of eigenforms with manual navigation.

Like ChainForm but without auto-advance. Steps must be completed
in order — step N+1 is only accessible when step N is complete.
The user manually navigates between steps using Next/Back affordances.
Completed steps can always be revisited.

Comparison:
    TabForm:       free access to all tabs, no ordering.
    SequenceForm:  gated sequential access, manual navigation.
    ChainForm:     gated sequential access, auto-advances on completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance, SwitchTabAffordance
from engine.eigenform import Eigenform
from engine.store import Store


@dataclass
class SequenceForm(Eigenform):
    """A gated sequence of eigenforms shown one at a time.

    Navigation rules:
    - Step 0 is always accessible.
    - Step N is accessible when step N-1 is complete.
    - The active step persists across page loads.
    - Completed steps can always be revisited.
    - No auto-advance: the user must explicitly navigate forward.
    """
    steps: list[Eigenform] = field(default_factory=list)

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["steps"] = [ef.to_descriptor() for ef in self.steps]
        return desc

    @property
    def children(self) -> list[Eigenform]:
        return self.steps

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.steps)

    def _highest_accessible_index(self) -> int:
        """The highest step index the user can navigate to."""
        for i, ef in enumerate(self.steps):
            if not ef.is_complete:
                return i
        return len(self.steps) - 1

    def _is_accessible(self, index: int) -> bool:
        """Whether step at index is accessible (all prior steps complete)."""
        return index <= self._highest_accessible_index()

    @property
    def _active_key(self) -> str | None:
        """The stored active step key."""
        stored = self.value
        if stored and stored in {ef.key for ef in self.steps}:
            return stored
        return None

    @property
    def active_step(self) -> Eigenform | None:
        """The currently visible step."""
        active_key = self._active_key
        if active_key:
            for i, ef in enumerate(self.steps):
                if ef.key == active_key and self._is_accessible(i):
                    return ef
        # Default to first step
        return self.steps[0] if self.steps else None

    @property
    def active_index(self) -> int:
        active = self.active_step
        if active:
            for i, ef in enumerate(self.steps):
                if ef.key == active.key:
                    return i
        return 0

    def _bind_children(self, store: Store, url_prefix: str):
        self.steps = [
            ef.bind(store=store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
            for ef in self.steps
        ]

    def _serialize_state(self) -> dict:
        active = self.active_step
        highest = self._highest_accessible_index()
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "active_step": active.key if active else None,
            "progress": [
                {
                    "key": ef.key,
                    "label": ef.label,
                    "complete": ef.is_complete,
                    "accessible": i <= highest,
                }
                for i, ef in enumerate(self.steps)
            ],
        }

    def _serialize_full(self) -> dict:
        state = self._serialize_state()
        active = self.active_step
        state["eigenform"] = active.serialize() if active else None
        state["complete"] = self.is_complete
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def get_affordances(self) -> list[Affordance]:
        from engine.affordances import SimpleButtonAffordance
        affordances: list[Affordance] = []
        idx = self.active_index
        url = f"{self._url_prefix}/{self.key}"

        # Back: available if not on first step
        if idx > 0:
            prev = self.steps[idx - 1]
            affordances.append(SimpleButtonAffordance(
                label=f"\u2190 Back: {prev.label}",
                method="POST",
                url=url,
                body={"step": prev.key},
                instruction=f"Go back to {prev.label}.",
            ))

        # Next: available if current step is complete and there's a next step
        if idx < len(self.steps) - 1 and self.steps[idx].is_complete:
            nxt = self.steps[idx + 1]
            affordances.append(SimpleButtonAffordance(
                label=f"Next: {nxt.label} \u2192",
                method="POST",
                url=url,
                body={"step": nxt.key},
                instruction=f"Advance to {nxt.label}.",
            ))

        # Jump to any accessible completed step (except current)
        active = self.active_step
        highest = self._highest_accessible_index()
        for i, ef in enumerate(self.steps):
            if i <= highest and ef.key != (active.key if active else None):
                if ef.is_complete:
                    affordances.append(SwitchTabAffordance(
                        label=f"Go to {ef.label}",
                        method="POST",
                        url=url,
                        body={"step": ef.key},
                        instruction=f"Jump to completed step: {ef.label}.",
                    ))

        return affordances

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        active_key = data.get("active_step")
        progress = data.get("progress", [])
        affs = data.get("affordances", [])

        # Classify affordances by type
        nav_affs = []    # Back / Next buttons
        jump_affs = {}   # step_key -> "Go to" affordance
        for aff in affs:
            label = aff.get("label", "")
            step_key = aff.get("body", {}).get("step")
            if label.startswith("\u2190") or label.startswith("Next"):
                nav_affs.append(aff)
            elif step_key:
                jump_affs[step_key] = aff

        # Progress bar with step indicators
        total = len(progress)
        html += '<div style="display: flex; align-items: center; gap: 2px; margin-bottom: 12px; flex-wrap: wrap;">'
        for i, step in enumerate(progress):
            is_active = step["key"] == active_key
            is_complete = step["complete"]
            is_accessible = step.get("accessible", False)

            if is_active:
                style = (
                    "font-weight: bold; padding: 4px 10px;"
                    " border-bottom: 3px solid #333; background: #f0f0f0;"
                    " border-radius: 3px 3px 0 0;"
                )
                html += f'<span style="{style}">{escape(step["label"])}</span>'
            elif is_complete and step["key"] in jump_affs:
                html += render_affordance_html(jump_affs[step["key"]])
            elif is_complete:
                html += (
                    f'<span style="padding: 4px 10px; color: #2a2; background: #efffef;'
                    f' border-radius: 3px;">&#10003; {escape(step["label"])}</span>'
                )
            elif is_accessible:
                style = "padding: 4px 10px; color: #555; background: #f8f8f8; border-radius: 3px;"
                html += f'<span style="{style}">{escape(step["label"])}</span>'
            else:
                style = "padding: 4px 10px; color: #bbb; background: #f5f5f5; border-radius: 3px;"
                html += f'<span style="{style}">&#128274; {escape(step["label"])}</span>'

            if i < total - 1:
                html += '<span style="color: #ccc; margin: 0 2px;">&#8594;</span>'

        html += '</div>'

        # Nav buttons (Back / Next)
        if nav_affs:
            html += '<div style="display: flex; gap: 8px; margin-bottom: 8px;">'
            for aff in nav_affs:
                html += render_affordance_html(aff)
            html += '</div>'

        # Active step content
        active = self.active_step
        if active:
            html += active.render()

        return html

    def _handle(self, body: dict) -> dict:
        """Handle step navigation."""
        step_key = body.get("step")
        if step_key:
            for i, ef in enumerate(self.steps):
                if ef.key == step_key and self._is_accessible(i):
                    self._store.set(self._scope, self.key, step_key)
                    break
        return self.serialize()
