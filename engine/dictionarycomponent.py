"""DictionaryComponent — dynamic set of key-value pairs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from engine.affordances import Affordance
from engine.component import Component
from engine.templates import render_template


class KVAddAffordance(Affordance):
    """An affordance for adding a key-value pair with two inputs."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 key_label: str = "Key", value_label: str = "Value"):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.key_label = key_label
        self.value_label = value_label

    def _render_hints(self) -> dict:
        return {"type": "kv_input_add", "key_label": self.key_label, "value_label": self.value_label}


@dataclass
class DictionaryComponent(Component):
    """A dynamic set of key-value pairs with stable IDs."""
    key_label: str = "Key"
    value_label: str = "Value"

    @property
    def _state(self) -> dict:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored
        return {"entries": [], "next_id": 0}

    @property
    def entries(self) -> list[dict]:
        return self._state.get("entries", [])

    @property
    def is_complete(self) -> bool:
        entries = self.entries
        if not entries:
            return False
        return all(e.get("key") and e.get("value") for e in entries)

    def _serialize_state(self) -> dict:
        # Strip internal IDs from agent-facing output — keys are the identifier
        clean_entries = [{"key": e["key"], "value": e["value"]} for e in self.entries]
        return self._base_state() | {
            "entries": clean_entries,
            "key_label": self.key_label,
            "value_label": self.value_label,
        }

    def get_affordances(self) -> list[Affordance]:
        affordances: list[Affordance] = []
        affordances.append(KVAddAffordance(
            label="Add Entry",
            method="POST",
            url=self.url,
            body={"action": "add", "key": f"<{self.key_label}>", "value": f"<{self.value_label}>"},
            instruction=f"Add a new key-value pair.",
            key_label=self.key_label,
            value_label=self.value_label,
        ))
        if self.entries:
            entry_keys = " | ".join(e["key"] for e in self.entries if e.get("key"))
            if entry_keys:
                affordances.append(Affordance(
                    label="Edit Entry",
                    method="POST",
                    url=self.url,
                    body={"action": "edit", "key": f"<{entry_keys}>",
                          "new_key": f"<optional new key>", "value": f"<{self.value_label}>"},
                    instruction="Edit an entry by key. Include new_key to rename. Omit new_key or value to keep unchanged.",
                ))
                affordances.append(Affordance(
                    label="Remove Entry",
                    method="POST",
                    url=self.url,
                    body={"action": "remove", "key": f"<{entry_keys}>"},
                    instruction="Remove an entry by key.",
                ))
        return affordances

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        affs.append(Affordance(
            label="Set Key Label", method="POST", url=self.url,
            body={"action": "set_key_label", "value": "<string>"},
            instruction=f"Set the label for keys. Current: {self.key_label}",
        ))
        affs.append(Affordance(
            label="Set Value Label", method="POST", url=self.url,
            body={"action": "set_value_label", "value": "<string>"},
            instruction=f"Set the label for values. Current: {self.value_label}",
        ))
        return affs

    def render_from_data(self, data: dict) -> str:
        return render_template("dictionary.html", data=data, ef=self,
                               url=self.url)

    def _handle(self, body: dict) -> dict:
        action = body.get("action")

        # Edit-mode config actions
        if action in ("set_key_label", "set_value_label") and self.editable and self.edit_mode:
            self._push_undo()
            raw = body.get("value", "").strip()
            if not raw:
                return self._error("Label cannot be empty", body=body)
            field = "key_label" if action == "set_key_label" else "value_label"
            self._set_my_config(field, raw)
            return self.serialize()

        state = self._state

        if action == "add":
            k = body.get("key", "")
            v = body.get("value", "")
            if not k or k.startswith("<"):
                return self._error("Key is required.", action=action)
            existing = {e["key"] for e in state["entries"]}
            if k in existing:
                return self._error(f"Key '{k}' already exists.", action=action)
            eid = f"kv_{state.get('next_id', 0)}"
            state["entries"].append({"id": eid, "key": k, "value": v})
            state["next_id"] = state.get("next_id", 0) + 1
            self._store.set(self._scope, self.key, state)
            return self.serialize()

        elif action == "edit":
            target_key = body.get("key", "")
            entry = next((e for e in state["entries"] if e["key"] == target_key), None)
            if entry is None:
                existing_keys = [e["key"] for e in state["entries"] if e.get("key")]
                return self._error(f"No entry with key {target_key!r}. Valid: {', '.join(existing_keys)}", action=action)
            new_key = body.get("new_key")
            if new_key and not new_key.startswith("<"):
                existing = {e["key"] for e in state["entries"] if e["key"] != target_key}
                if new_key in existing:
                    return self._error(f"Key '{new_key}' already exists on another entry.", action=action)
                entry["key"] = new_key
            v = body.get("value")
            if v and not v.startswith("<"):
                entry["value"] = v
            self._store.set(self._scope, self.key, state)
            return self.serialize()

        elif action == "remove":
            target_key = body.get("key", "")
            before = len(state["entries"])
            state["entries"] = [e for e in state["entries"] if e["key"] != target_key]
            if len(state["entries"]) == before:
                existing_keys = [e["key"] for e in state["entries"] if e.get("key")]
                return self._error(f"No entry with key {target_key!r}. Valid: {', '.join(existing_keys)}", action=action)
            self._store.set(self._scope, self.key, state)
            return self.serialize()

        return self._error(f"Unknown action: {action}", action=action)
