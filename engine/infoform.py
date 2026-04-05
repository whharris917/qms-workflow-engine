"""InfoForm — read-only text display.

Edit mode allows modifying the text content:
- String mode: set the text string
- Dict mode: add, edit, or remove labeled entries
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.affordances import Affordance, SetValueAffordance, SimpleButtonAffordance
from engine.eigenform import Eigenform
from engine.templates import render_template


@dataclass
class InfoForm(Eigenform):
    """Display-only text. No interaction affordances, always complete.

    text can be a string (rendered as-is) or a dict (rendered as labeled
    key-value pairs in HTML, structured fields in JSON).

    Edit mode allows modifying the text content via _effective_text.
    """
    text: str | dict = ""

    @property
    def is_complete(self) -> bool:
        return True

    # --- Edit mode config ---

    def _snapshot_edit_state(self) -> dict:
        state = super()._snapshot_edit_state()
        state["__config"] = self._store.get(self._scope, f"{self.key}.__config")
        return state

    def _restore_edit_state(self, state: dict):
        super()._restore_edit_state(state)
        self._store.set(self._scope, f"{self.key}.__config", state.get("__config"))

    @property
    def _effective_text(self) -> str | dict:
        if self._store is not None:
            override = self._store.get(self._scope, f"{self.key}.__config")
            if override is not None:
                return override.get("text", self.text)
        return self.text

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        text = self._effective_text

        if isinstance(text, dict):
            affs.append(SetValueAffordance(
                label="Set Entry",
                method="POST", url=self.url,
                body={"action": "set_entry", "key": "<label>", "value": "<text>"},
                instruction="Add or update a labeled entry.",
            ))
            for key in text:
                affs.append(SimpleButtonAffordance(
                    label=f"Remove Entry '{key}'",
                    method="POST", url=self.url,
                    body={"action": "remove_entry", "key": key},
                    instruction=f"Remove the '{key}' entry.",
                ))
        else:
            affs.append(SetValueAffordance(
                label="Set Text",
                method="POST", url=self.url,
                body={"action": "set_text", "value": "<text>"},
                instruction="Set the display text.",
            ))

        return affs

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")

        if self.edit_mode:
            if action == "set_text":
                self._push_undo()
                value = body.get("value", "")
                cfg = {"text": value}
                self._store.set(self._scope, f"{self.key}.__config", cfg)
                return self.serialize()

            elif action == "set_entry":
                self._push_undo()
                key = body.get("key")
                value = body.get("value", "")
                if not key:
                    return self._error("'key' is required.", action="set_entry")
                text = self._effective_text
                if not isinstance(text, dict):
                    text = {}
                text = dict(text)
                text[key] = value
                self._store.set(self._scope, f"{self.key}.__config", {"text": text})
                return self.serialize()

            elif action == "remove_entry":
                self._push_undo()
                key = body.get("key")
                if not key:
                    return self._error("'key' is required.", action="remove_entry")
                text = self._effective_text
                if not isinstance(text, dict) or key not in text:
                    return self._error(f"Entry '{key}' not found.", action="remove_entry")
                text = dict(text)
                del text[key]
                self._store.set(self._scope, f"{self.key}.__config", {"text": text})
                return self.serialize()

        return self.serialize()

    # --- Serialization ---

    def _serialize_state(self) -> dict:
        return self._base_state() | {"text": self._effective_text}

    def get_affordances(self) -> list[Affordance]:
        return []

    def render_from_data(self, data: dict) -> str:
        return render_template(
            "info.html", data=data, ef=self, url=self.url,
            label=data.get("label", ""),
            instruction=data.get("instruction") or "",
        )
