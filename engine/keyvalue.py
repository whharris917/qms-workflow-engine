"""KeyValueForm — dynamic set of key-value pairs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from typing import Any

from engine.affordances import Affordance
from engine.eigenforms import Eigenform


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
class KeyValueForm(Eigenform):
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
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "entries": self.entries,
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
        for entry in self.entries:
            eid = entry["id"]
            affordances.append(Affordance(
                label=f"Edit {eid}",
                method="POST",
                url=self.url,
                body={"action": "edit", "id": eid, "key": f"<{self.key_label}>", "value": f"<{self.value_label}>"},
                instruction=f"Edit entry {eid}. Omit key or value to keep unchanged.",
            ))
            affordances.append(Affordance(
                label=f"Remove {eid}",
                method="POST",
                url=self.url,
                body={"action": "remove", "id": eid},
                instruction=f"Remove entry {eid}.",
            ))
        return affordances

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        entries = data.get("entries", [])
        affs = data.get("affordances", [])
        kl = escape(data.get("key_label", "Key"))
        vl = escape(data.get("value_label", "Value"))

        if entries:
            html += f'<table style="border-collapse: collapse; width: 100%;">'
            html += (f'<tr><th style="text-align: left; padding: 4px; border-bottom: 1px solid #ccc;">{kl}</th>'
                     f'<th style="text-align: left; padding: 4px; border-bottom: 1px solid #ccc;">{vl}</th>'
                     f'<th style="padding: 4px; border-bottom: 1px solid #ccc;"></th></tr>')
            for entry in entries:
                eid = entry["id"]
                html += (f'<tr><td style="padding: 4px; border-bottom: 1px solid #eee;">{escape(str(entry.get("key", "")))}</td>'
                         f'<td style="padding: 4px; border-bottom: 1px solid #eee;">{escape(str(entry.get("value", "")))}</td>'
                         f'<td style="padding: 4px; border-bottom: 1px solid #eee;">')
                # Inline remove button
                for aff in affs:
                    if aff.get("body", {}).get("action") == "remove" and aff.get("body", {}).get("id") == eid:
                        Eigenform.mark_rendered(aff)
                        body_js = json.dumps(aff["body"]).replace('"', '&quot;')
                        html += (
                            f'<button onclick="fetch(\'{aff["url"]}\','
                            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                            f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
                            f' style="cursor: pointer; font-size: 11px;" title="Remove">x</button>'
                        )
                        break
                # Mark edit affordance as rendered (agent-only)
                for aff in affs:
                    if aff.get("body", {}).get("action") == "edit" and aff.get("body", {}).get("id") == eid:
                        Eigenform.mark_rendered(aff)
                        break
                html += '</td></tr>'
            html += '</table>'
        else:
            html += '<p style="color: #888;">No entries.</p>'

        # Render add affordance
        for aff in affs:
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)

        return html

    def _handle(self, body: dict) -> dict:
        action = body.get("action")
        state = self._state

        if action == "add":
            k = body.get("key", "")
            v = body.get("value", "")
            if not k or k.startswith("<"):
                return self._error("add", "Key is required.")
            eid = f"kv_{state.get('next_id', 0)}"
            state["entries"].append({"id": eid, "key": k, "value": v})
            state["next_id"] = state.get("next_id", 0) + 1
            self._store.set(self._scope, self.key, state)
            return self.serialize()

        elif action == "edit":
            eid = body.get("id")
            for entry in state["entries"]:
                if entry["id"] == eid:
                    k = body.get("key")
                    v = body.get("value")
                    if k and not k.startswith("<"):
                        entry["key"] = k
                    if v and not v.startswith("<"):
                        entry["value"] = v
                    self._store.set(self._scope, self.key, state)
                    return self.serialize()
            return self._error("edit", f"Entry {eid} not found.")

        elif action == "remove":
            eid = body.get("id")
            state["entries"] = [e for e in state["entries"] if e["id"] != eid]
            self._store.set(self._scope, self.key, state)
            return self.serialize()

        return self._error(action, f"Unknown action: {action}")

    def _error(self, action: str, msg: str) -> dict:
        result = self.serialize()
        result["error"] = msg
        result["failed_action"] = action
        return result
