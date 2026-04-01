"""KeyValueForm — dynamic set of key-value pairs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from typing import Any

from engine.affordances import (
    Affordance, BUTTON_GAP, STYLE_CONFIRM, STYLE_REMOVE, render_inline_button,
)
from engine.eigenform import Eigenform


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
        html += f'<span style="display: inline-block; width: 24px;"></span>'
        html += f'<span style="width: 120px;">{kl}</span>'
        html += f'<span style="flex: 1;">{vl}</span>'
        html += f'</div>'

        # Existing entries — inline edit fields + ✓ + x
        for entry in entries:
            ekey = escape(str(entry.get("key", "")))
            ekey_raw = entry.get("key", "")
            ekey_js = ekey_raw.replace("\\", "\\\\").replace("'", "\\'")
            eval_ = escape(str(entry.get("value", "")))
            edit_tooltip_js = (
                f"var f=this.form;"
                f"var b={{action:'edit',key:'{ekey_js}'}};"
                f"if(f.elements.k.value!=='{ekey_js}')b.new_key=f.elements.k.value;"
                f"b.value=f.elements.v.value;"
                f"f.querySelector('button[type=submit]').title="
                f"'{escape(endpoint)} '+JSON.stringify(b)"
            )
            edit_default = {"action": "edit", "key": ekey_raw, "value": entry.get("value", "")}
            edit_tooltip = f'{escape(endpoint)} {escape(json.dumps(edit_default))}'
            html += f'<div style="display: flex; align-items: center; gap: 4px; margin: 2px 0;">'
            html += render_inline_button(url, {"action": "remove", "key": ekey_raw}, "x", STYLE_REMOVE)
            html += (
                f'<form style="display: contents; margin: 0;" onsubmit="'
                f"var b={{action:'edit',key:'{ekey_js}'}};"
                f"if(this.elements.k.value!=='{ekey_js}')b.new_key=this.elements.k.value;"
                f"b.value=this.elements.v.value;"
                f"fetch('{url}',"
                f"{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
                f'<input name="k" type="text" value="{ekey}" style="border: 1px solid #ddd; padding: 2px 4px; width: 120px;"'
                f' oninput="{edit_tooltip_js}" />'
                f'<input name="v" type="text" value="{eval_}" style="border: 1px solid #ddd; padding: 2px 4px; flex: 1;"'
                f' oninput="{edit_tooltip_js}" />'
                f'<button type="submit" style="{STYLE_CONFIRM}"'
                f' title="{edit_tooltip}">&#10003;</button>'
                f'</form>'
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
        gap = BUTTON_GAP
        html += (
            f'<div style="display: flex; align-items: center; gap: 4px; margin: 2px 0;">'
            f'{gap}'
            f'<form style="display: contents; margin: 0;" onsubmit="fetch(\'{url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f"body:JSON.stringify({{action:'add',key:this.elements.k.value,value:this.elements.v.value}})"
            f'}}).then(()=>location.reload()); return false">'
            f'<input name="k" type="text" placeholder="{kl}" style="border: 1px solid #ddd; padding: 2px 4px; width: 120px;"'
            f' oninput="{add_tooltip_js}" />'
            f'<input name="v" type="text" placeholder="{vl}" style="border: 1px solid #ddd; padding: 2px 4px; flex: 1;"'
            f' oninput="{add_tooltip_js}" />'
            f'<button type="submit" style="{STYLE_CONFIRM}"'
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
