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
from engine.eigenforms import Eigenform
from engine.store import Store


@dataclass
class ChainForm(Eigenform):
    """A sequence of eigenforms, auto-advancing through them one at a time."""
    steps: list[Eigenform] = field(default_factory=list)

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
        # Auto-focus: first incomplete step
        for ef in self.steps:
            if not ef.is_complete:
                return ef
        # All complete: show the last one
        return self.steps[-1] if self.steps else None

    @property
    def active_key(self) -> str | None:
        active = self.active_step
        return active.key if active else None

    def bind(self, store: Store, scope: str, url_prefix: str) -> ChainForm:
        import copy
        bound = copy.deepcopy(self)
        bound._store = store
        bound._scope = scope
        bound._url_prefix = url_prefix
        bound.steps = [
            ef.bind(store=store, scope=bound.key, url_prefix=url_prefix)
            for ef in self.steps
        ]
        return bound

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

    def serialize(self) -> dict:
        state = self._serialize_state()
        active = self.active_step
        state["eigenform"] = active.serialize() if active else None
        state["complete"] = self.is_complete
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def get_affordances(self) -> list[Affordance]:
        affordances: list[Affordance] = []
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

    def render_inner(self, affordances: list[Affordance]) -> str:
        html = f'<h3>{self.label}</h3>'
        if self.instruction:
            html += f'<p>{self.instruction}</p>'

        # Progress bar
        html += '<div style="margin-bottom: 8px;">'
        for ef in self.steps:
            is_active = ef.key == self.active_key
            if ef.is_complete and not is_active:
                # Completed: render as jump-back affordance
                for aff in affordances:
                    if aff.body.get("focus") == ef.key:
                        html += aff.render()
                        break
            elif is_active:
                html += (
                    f'<span style="font-weight: bold; margin-right: 4px;'
                    f' padding: 2px 8px; border-bottom: 2px solid #333;">'
                    f'{escape(ef.label)}</span>'
                )
            else:
                html += (
                    f'<span style="margin-right: 4px; padding: 2px 8px;'
                    f' color: #aaa;">{escape(ef.label)}</span>'
                )
        html += '</div>'

        # Active step
        active = self.active_step
        if active:
            html += active.render()

        return html

    def handle(self, body: dict) -> dict:
        """Handle focus change."""
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
