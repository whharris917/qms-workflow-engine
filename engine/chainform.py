"""ChainForm — a sequence of eigenforms shown one at a time.

Only the first incomplete eigenform is visible. Completed eigenforms
appear as "jump back" affordances, allowing revisitation. Both the
agent and human see the same thing — faithful projection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance, SwitchTabAffordance
from engine.eigenform import Eigenform
from engine.store import Store


@dataclass
class ChainForm(Eigenform):
    """A sequence of eigenforms, auto-advancing through them one at a time."""
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

    @property
    def _focused_key(self) -> str | None:
        """The key of the currently focused step, from the store."""
        stored = self.value
        if stored and stored in {ef.key for ef in self.steps}:
            return stored
        return None

    @property
    def active_step(self) -> Eigenform | None:
        """The currently visible step: explicitly focused, or first incomplete."""
        focused = self._focused_key
        if focused:
            for ef in self.steps:
                if ef.key == focused:
                    return ef
        for ef in self.steps:
            if not ef.is_complete:
                return ef
        return self.steps[-1] if self.steps else None

    @property
    def active_key(self) -> str | None:
        active = self.active_step
        return active.key if active else None

    def _bind_children(self, store: Store, url_prefix: str):
        self.steps = [
            ef.bind(store=store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
            for ef in self.steps
        ]

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "active_step": self.active_key,
            "progress": [
                {"key": ef.key, "label": ef.label, "complete": ef.is_complete}
                for ef in self.steps
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
        active = self.active_step
        # If viewing a completed step (jumped back), offer Continue
        if active and active.is_complete and self._focused_key is not None:
            affordances.append(SimpleButtonAffordance(
                label="Continue",
                method="POST",
                url=f"{self._url_prefix}/{self.key}",
                body={"action": "continue"},
                instruction="Resume from the next incomplete step.",
            ))
        for ef in self.steps:
            if ef.is_complete and ef.key != self.active_key:
                affordances.append(SwitchTabAffordance(
                    label=f"Back to {ef.label}",
                    method="POST",
                    url=f"{self._url_prefix}/{self.key}",
                    body={"focus": ef.key},
                    instruction=f"Jump back to the completed {ef.label} step.",
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

        # Progress bar
        html += '<div style="margin-bottom: 8px;">'
        for step in progress:
            if step["complete"] and step["key"] != active_key:
                # Completed: render as jump-back affordance
                for aff in affs:
                    if aff.get("body", {}).get("focus") == step["key"]:
                        html += render_affordance_html(aff)
                        break
            elif step["key"] == active_key:
                html += (
                    f'<span style="font-weight: bold; margin-right: 4px;'
                    f' padding: 2px 8px; border-bottom: 2px solid #333;">'
                    f'{escape(step["label"])}</span>'
                )
            else:
                html += (
                    f'<span style="margin-right: 4px; padding: 2px 8px;'
                    f' color: #aaa;">{escape(step["label"])}</span>'
                )
        # Render any remaining affordances (e.g. Continue button)
        for aff in affs:
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'

        # Active step
        active = self.active_step
        if active:
            html += active.render()

        return html

    def _handle(self, body: dict) -> dict:
        """Handle focus change or continue."""
        if body.get("action") == "continue":
            self._store.set(self._scope, self.key, None)
            return self.serialize()
        focus = body.get("focus")
        if focus and focus in {ef.key for ef in self.steps}:
            self._store.set(self._scope, self.key, focus)
        return self.serialize()

    def handle_action(self, key: str, body: dict) -> bool:
        """Route action: focus change goes to self, otherwise to active step."""
        if key == self.key:
            self.handle(body)
            # After handling focus, clear it if the target is complete
            # so auto-focus resumes
            return True
        active = self.active_step
        if active and active.key == key:
            active.handle(body)
            # Clear explicit focus so auto-advance kicks in
            self._store.set(self._scope, self.key, None)
            return True
        return False
