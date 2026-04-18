"""InfoDisplay — read-only text display.

Edit mode exposes an embedded TextForm (multiline) for editing the content.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.affordances import Affordance
from engine.component import Component
from engine.templates import render_template


@dataclass
class InfoDisplay(Component):
    """Display-only text. No interaction affordances, always complete.

    Edit mode embeds a multiline TextForm for content editing.
    """
    form = "info"

    text: str | dict = ""  # dict is converted to "key: value" lines on bind

    def __post_init__(self):
        from engine.textform import TextForm
        self._text_form = TextForm(
            key="__text",
            label="Content",
            multiline=True,
        )

    @property
    def children(self) -> list[Component]:
        if self.edit_mode:
            return [self._text_form]
        return []

    def _bind_children(self, store, url_prefix):
        self._text_form = self._text_form.bind(
            store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
        # Seed from self.text if no data yet
        if not self._text_form.value and self.text:
            seed = self.text
            if isinstance(seed, dict):
                seed = "\n".join(f"{k}: {v}" for k, v in seed.items())
            self._text_form.handle({"value": seed})
        # Wrap child handle so InfoDisplay pushes undo before TextForm changes
        original_handle = self._text_form.handle
        parent = self
        def _handle_with_undo(body):
            if parent.edit_mode:
                parent._push_undo()
            return original_handle(body)
        self._text_form.handle = _handle_with_undo

    @property
    def is_complete(self) -> bool:
        return True

    def _snapshot_edit_state(self) -> dict:
        state = super()._snapshot_edit_state()
        state["__text"] = self._store.get(self.key, "__text")
        return state

    def _restore_edit_state(self, state: dict):
        super()._restore_edit_state(state)
        self._store.set(self.key, "__text", state.get("__text"))

    @property
    def _effective_text(self) -> str:
        val = self._text_form.value
        if val:
            return val
        if isinstance(self.text, dict):
            return "\n".join(f"{k}: {v}" for k, v in self.text.items())
        return self.text

    def _serialize_full(self) -> dict:
        state = super()._serialize_full()
        # InfoDisplay has no interaction affordances — Batch is meaningless
        state["affordances"] = [
            a for a in state.get("affordances", [])
            if a.get("body", {}).get("action") != "batch"
        ]
        return state

    def _serialize_state(self) -> dict:
        return self._base_state() | {"text": self._effective_text}

    def get_affordances(self) -> list[Affordance]:
        return []

    def render_from_data(self, data: dict) -> str:
        text_html = self._text_form.render_safely() if data.get("edit_mode") else ""
        return render_template(
            "info.html", data=data, ef=self, url=self.url,
            label=data.get("label", ""),
            instruction=data.get("instruction") or "",
            text_html=text_html,
        )
