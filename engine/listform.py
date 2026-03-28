"""ListForm — an ordered list of items with add/remove/reorder."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.store import Store
from engine.eigenforms import Eigenform


class AddItemAffordance(Affordance):
    """An affordance that adds an item to the list."""

    def _render_hints(self) -> dict:
        return {"type": "text_input_add", "placeholder": "New item"}


@dataclass
class ListForm(Eigenform):
    """An ordered list of string items with add, remove, edit, and reorder."""

    @property
    def items(self) -> list[dict]:
        """List of items: [{"id": "item_0", "value": "..."}, ...]"""
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored.get("items", [])
        return []

    @property
    def _next_id(self) -> int:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored.get("next_id", 0)
        return 0

    @property
    def na(self) -> bool:
        stored = self.value
        if stored and isinstance(stored, dict):
            return bool(stored.get("__na"))
        return False

    @property
    def is_complete(self) -> bool:
        return self.na or len(self.items) > 0

    def _save(self, items: list[dict], next_id: int | None = None):
        self._store.set(self._scope, self.key, {
            "items": items,
            "next_id": next_id if next_id is not None else self._next_id,
        })

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "items": self.items,
            "count": len(self.items),
            "na": self.na,
        }

    def get_affordances(self) -> list[Affordance]:
        if self.na:
            return [
                SimpleButtonAffordance(
                    label="Clear N/A",
                    method="POST",
                    url=self.url,
                    body={"action": "clear_na"},
                    instruction="Clear N/A and allow adding items.",
                )
            ]

        affordances: list[Affordance] = []
        item_ids = " | ".join(i["id"] for i in self.items) if self.items else ""

        affordances.append(AddItemAffordance(
            label="+ Add",
            method="POST",
            url=self.url,
            body={"action": "add", "value": "<item text>"},
            instruction=f"Add a new item to the {self.label} list.",
        ))

        if self.items:
            affordances.append(Affordance(
                label="Edit Item",
                method="POST",
                url=self.url,
                body={"action": "edit", "id": f"<{item_ids}>", "value": "<new value>"},
                instruction="Edit an existing item by ID.",
            ))

            affordances.append(Affordance(
                label="Remove Item",
                method="POST",
                url=self.url,
                body={"action": "remove", "id": f"<{item_ids}>"},
                instruction="Remove an item by ID.",
            ))

        if len(self.items) > 1:
            for item in self.items:
                idx = next(i for i, it in enumerate(self.items) if it["id"] == item["id"])
                if idx > 0:
                    affordances.append(SimpleButtonAffordance(
                        label=f"Move {item['id']} up",
                        method="POST",
                        url=self.url,
                        body={"action": "move", "id": item["id"], "position": idx - 1},
                        instruction=f"Move {item['id']} up one position.",
                    ))
                if idx < len(self.items) - 1:
                    affordances.append(SimpleButtonAffordance(
                        label=f"Move {item['id']} down",
                        method="POST",
                        url=self.url,
                        body={"action": "move", "id": item["id"], "position": idx + 1},
                        instruction=f"Move {item['id']} down one position.",
                    ))

        affordances.append(SimpleButtonAffordance(
            label="N/A",
            method="POST",
            url=self.url,
            body={"action": "na"},
            instruction=f"Mark {self.label} as not applicable. Removes all items.",
        ))

        return affordances

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        affs = data.get("affordances", [])

        if data.get("na"):
            html += '<p style="color: #888; font-style: italic;">N/A</p>'
            for aff in affs:
                html += render_affordance_html(aff)
            return html

        items = data.get("items", [])

        # Build lookups and mark agent-only affordances as rendered
        from engine.eigenforms import Eigenform
        move_affs: dict[str, list[dict]] = {}
        add_aff = None
        url = affs[0]["url"] if affs else ""
        for aff in affs:
            action = aff.get("body", {}).get("action")
            if action == "move":
                item_id = aff["body"].get("id")
                move_affs.setdefault(item_id, []).append(aff)
                Eigenform.mark_rendered(aff)
            elif action in ("edit", "remove"):
                Eigenform.mark_rendered(aff)
            elif action == "add":
                add_aff = aff
                Eigenform.mark_rendered(aff)

        endpoint = f'POST {url}'
        html += '<ol style="margin: 4px 0; padding-left: 24px;">'

        # Existing items
        for idx, item in enumerate(items):
            item_id = item["id"]
            item_val = escape(str(item.get("value", "")))
            edit_tooltip_js = (
                f"this.nextElementSibling.title="
                f"'{escape(endpoint)} '+JSON.stringify({{action:'edit',id:'{item_id}',value:this.value}})"
            )
            edit_default = {"action": "edit", "id": item_id, "value": item.get("value", "")}
            edit_tooltip = f'{escape(endpoint)} {escape(json.dumps(edit_default))}'
            html += (
                f'<li style="margin: 4px 0; display: flex; align-items: center; gap: 4px;">'
                f'<form style="display: inline; margin: 0;" onsubmit="fetch(\'{url}\','
                f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f"body:JSON.stringify({{action:'edit',id:'{item_id}',value:this.elements.v.value}})"
                f'}}).then(()=>location.reload()); return false">'
                f'<input name="v" type="text" value="{item_val}"'
                f' style="border: 1px solid #ddd; padding: 2px 4px; width: 200px;"'
                f' oninput="{edit_tooltip_js}" />'
                f' <button type="submit"'
                f' style="cursor: pointer; border: 1px solid #4a4; background: #efffef;'
                f' width: 24px; height: 24px; font-size: 14px; padding: 0; color: #2a2;"'
                f' title="{edit_tooltip}">&#10003;</button>'
                f'</form>'
            )
            # Move up/down buttons inline
            for maff in move_affs.get(item_id, []):
                direction = "up" if maff["body"].get("position", 0) < idx else "down"
                arrow = "&#9650;" if direction == "up" else "&#9660;"
                body_js = json.dumps(maff["body"]).replace('"', '&quot;')
                tooltip = f'{escape(endpoint)} {escape(json.dumps(maff["body"]))}'
                html += (
                    f'<button onclick="fetch(\'{url}\','
                    f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                    f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
                    f' style="cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;'
                    f' width: 24px; height: 24px; font-size: 10px; padding: 0;"'
                    f' title="{tooltip}">{arrow}</button>'
                )
            # Remove button inline
            remove_body = {"action": "remove", "id": item_id}
            body_js = json.dumps(remove_body).replace('"', '&quot;')
            tooltip = f'{escape(endpoint)} {escape(json.dumps(remove_body))}'
            html += (
                f'<button onclick="fetch(\'{url}\','
                f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
                f' style="cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;'
                f' width: 24px; height: 24px; font-size: 12px; padding: 0; color: #c00;"'
                f' title="{tooltip}">x</button>'
            )
            html += f' <span style="font-size: 10px; color: #888;">{escape(item_id)}</span>'
            html += '</li>'

        # Add row — inline text field + green + button
        if add_aff:
            add_default = {"action": "add", "value": ""}
            add_tooltip = f'{escape(endpoint)} {escape(json.dumps(add_default))}'
            add_tooltip_js = (
                f"this.nextElementSibling.title="
                f"'{escape(endpoint)} '+JSON.stringify({{action:'add',value:this.value}})"
            )
            html += (
                f'<li style="margin: 4px 0; display: flex; align-items: center; gap: 4px; list-style: none;">'
                f'<form style="display: inline; margin: 0;" onsubmit="fetch(\'{url}\','
                f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f"body:JSON.stringify({{action:'add',value:this.elements.v.value}})"
                f'}}).then(()=>location.reload()); return false">'
                f'<input name="v" type="text" placeholder="New item"'
                f' style="border: 1px solid #ddd; padding: 2px 4px; width: 200px;"'
                f' oninput="{add_tooltip_js}" />'
                f' <button type="submit"'
                f' style="cursor: pointer; border: 1px solid #4a4; background: #efffef;'
                f' width: 24px; height: 24px; font-size: 14px; padding: 0; color: #2a2;"'
                f' title="{add_tooltip}">+</button>'
                f'</form>'
                f'</li>'
            )

        html += '</ol>'

        # Bottom controls: render remaining affordances (N/A, Clear, etc.)
        html += '<div style="margin-top: 8px;">'
        for aff in affs:
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'

        return html

    def _error(self, action: str, msg: str) -> dict:
        result = self.serialize()
        result["error"] = msg
        result["failed_action"] = action
        return result

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")
        items = [dict(i) for i in self.items]
        next_id = self._next_id
        item_ids = {i["id"] for i in items}

        if action == "add":
            value = body.get("value", "").strip()
            if not value:
                return self._error(action, "Item value is required.")
            item_id = f"item_{next_id}"
            next_id += 1
            items.append({"id": item_id, "value": value})
            self._save(items, next_id)

        elif action == "edit":
            item_id = body.get("id", "")
            value = body.get("value", "")
            if item_id not in item_ids:
                return self._error(action, f"Unknown item: {item_id}. Valid: {', '.join(item_ids)}")
            for item in items:
                if item["id"] == item_id:
                    item["value"] = value
                    break
            self._save(items, next_id)

        elif action == "remove":
            item_id = body.get("id", "")
            if item_id not in item_ids:
                return self._error(action, f"Unknown item: {item_id}. Valid: {', '.join(item_ids)}")
            items = [i for i in items if i["id"] != item_id]
            self._save(items, next_id)

        elif action == "move":
            item_id = body.get("id", "")
            position = body.get("position")
            if isinstance(position, str) and position.isdigit():
                position = int(position)
            if item_id not in item_ids:
                return self._error(action, f"Unknown item: {item_id}. Valid: {', '.join(item_ids)}")
            if not isinstance(position, int) or position < 0 or position >= len(items):
                return self._error(action, f"Invalid position: {position}. Valid: 0 to {len(items) - 1}")
            item = next(i for i in items if i["id"] == item_id)
            items = [i for i in items if i["id"] != item_id]
            items.insert(position, item)
            self._save(items, next_id)

        elif action == "na":
            self._store.set(self._scope, self.key, {"items": [], "next_id": next_id, "__na": True})

        elif action == "clear_na":
            self._store.set(self._scope, self.key, {"items": [], "next_id": next_id})

        else:
            return self._error(action, f"Unknown action: {action}")

        return self.serialize()
