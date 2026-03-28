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
        if self.entries:
            entry_ids = " | ".join(e["id"] for e in self.entries)
            affordances.append(Affordance(
                label="Edit Entry",
                method="POST",
                url=self.url,
                body={"action": "edit", "id": f"<{entry_ids}>",
                      "key": f"<{self.key_label}>", "value": f"<{self.value_label}>"},
                instruction="Edit an entry by ID. Omit key or value to keep unchanged.",
            ))
            affordances.append(Affordance(
                label="Remove Entry",
                method="POST",
                url=self.url,
                body={"action": "remove", "id": f"<{entry_ids}>"},
                instruction="Remove an entry by ID.",
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

        # Mark condensed edit/remove/add affordances as rendered (inline UI handles display)
        url = affs[0]["url"] if affs else ""
        endpoint = f'POST {url}'
        for aff in affs:
            action = aff.get("body", {}).get("action")
            if action in ("edit", "remove", "add"):
                Eigenform.mark_rendered(aff)

        html += f'<div style="display: flex; gap: 4px; margin: 4px 0; font-weight: bold; font-size: 0.9em;">'
        html += f'<span style="width: 120px;">{kl}</span>'
        html += f'<span style="flex: 1;">{vl}</span>'
        html += f'</div>'

        # Existing entries — inline edit fields + ✓ + x
        for entry in entries:
            eid = entry["id"]
            ekey = escape(str(entry.get("key", "")))
            eval_ = escape(str(entry.get("value", "")))
            edit_tooltip_js = (
                f"var f=this.form;"
                f"f.querySelector('button[type=submit]').title="
                f"'{escape(endpoint)} '+JSON.stringify({{action:'edit',id:'{eid}',key:f.elements.k.value,value:f.elements.v.value}})"
            )
            edit_default = {"action": "edit", "id": eid, "key": entry.get("key", ""), "value": entry.get("value", "")}
            edit_tooltip = f'{escape(endpoint)} {escape(json.dumps(edit_default))}'
            remove_body = {"action": "remove", "id": eid}
            remove_js = json.dumps(remove_body).replace('"', '&quot;')
            remove_tooltip = f'{escape(endpoint)} {escape(json.dumps(remove_body))}'
            html += (
                f'<div style="display: flex; align-items: center; gap: 4px; margin: 2px 0;">'
                f'<form style="display: contents; margin: 0;" onsubmit="fetch(\'{url}\','
                f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f"body:JSON.stringify({{action:'edit',id:'{eid}',key:this.elements.k.value,value:this.elements.v.value}})"
                f'}}).then(()=>location.reload()); return false">'
                f'<input name="k" type="text" value="{ekey}" style="border: 1px solid #ddd; padding: 2px 4px; width: 120px;"'
                f' oninput="{edit_tooltip_js}" />'
                f'<input name="v" type="text" value="{eval_}" style="border: 1px solid #ddd; padding: 2px 4px; flex: 1;"'
                f' oninput="{edit_tooltip_js}" />'
                f'<button type="submit"'
                f' style="cursor: pointer; border: 1px solid #4a4; background: #efffef;'
                f' width: 24px; height: 24px; font-size: 14px; padding: 0; color: #2a2;"'
                f' title="{edit_tooltip}">&#10003;</button>'
                f'</form>'
                f'<button onclick="fetch(\'{url}\','
                f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f'body:JSON.stringify({remove_js})}}).then(()=>location.reload())"'
                f' style="cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;'
                f' width: 24px; height: 24px; font-size: 12px; padding: 0; color: #c00;"'
                f' title="{remove_tooltip}">x</button>'
                f'</div>'
            )

        # Add row — inline key + value fields + green + button
        add_default = {"action": "add", "key": "", "value": ""}
        add_tooltip = f'{escape(endpoint)} {escape(json.dumps(add_default))}'
        add_tooltip_js = (
            f"var f=this.form;"
            f"f.querySelector('button[type=submit]').title="
            f"'{escape(endpoint)} '+JSON.stringify({{action:'add',key:f.elements.k.value,value:f.elements.v.value}})"
        )
        html += (
            f'<div style="display: flex; align-items: center; gap: 4px; margin: 2px 0;">'
            f'<form style="display: contents; margin: 0;" onsubmit="fetch(\'{url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f"body:JSON.stringify({{action:'add',key:this.elements.k.value,value:this.elements.v.value}})"
            f'}}).then(()=>location.reload()); return false">'
            f'<input name="k" type="text" placeholder="{kl}" style="border: 1px solid #ddd; padding: 2px 4px; width: 120px;"'
            f' oninput="{add_tooltip_js}" />'
            f'<input name="v" type="text" placeholder="{vl}" style="border: 1px solid #ddd; padding: 2px 4px; flex: 1;"'
            f' oninput="{add_tooltip_js}" />'
            f'<button type="submit"'
            f' style="cursor: pointer; border: 1px solid #4a4; background: #efffef;'
            f' width: 24px; height: 24px; font-size: 14px; padding: 0; color: #2a2;"'
            f' title="{add_tooltip}">+</button>'
            f'</form>'
            f'</div>'
        )

        # Render remaining affordances (Clear, etc.)
        html += '<div style="margin-top: 8px;">'
        for aff in affs:
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'

        return html

    def _handle(self, body: dict) -> dict:
        action = body.get("action")
        state = self._state

        if action == "add":
            k = body.get("key", "")
            v = body.get("value", "")
            if not k or k.startswith("<"):
                return self._error("add", "Key is required.")
            existing = {e["key"] for e in state["entries"]}
            if k in existing:
                return self._error("add", f"Key '{k}' already exists.")
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
                        existing = {e["key"] for e in state["entries"] if e["id"] != eid}
                        if k in existing:
                            return self._error("edit", f"Key '{k}' already exists on another entry.")
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
