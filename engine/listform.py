"""ListForm — an ordered list of items with add/remove/reorder."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import (
    Affordance, SimpleButtonAffordance,
    STYLE_CONFIRM, STYLE_REMOVE, STYLE_ARROW, render_inline_button,
)
from engine.eigenform import Eigenform


class AddItemAffordance(Affordance):
    """An affordance that adds an item to the list."""

    def _render_hints(self) -> dict:
        return {"type": "text_input_add", "placeholder": "New item"}


@dataclass
class ListForm(Eigenform):
    """An ordered list of string items with add, remove, edit, and reorder.

    If fixed_items is provided, those items are seeded into the list on
    first access and cannot be removed or renamed. They can be freely
    reordered alongside user-added items.
    """
    fixed_items: list[str] = field(default_factory=list)

    @property
    def items(self) -> list[dict]:
        """List of items: [{"id": "item_0", "value": "...", "fixed": bool}, ...]"""
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored.get("items", [])
        if self.fixed_items:
            return [{"id": f"item_{i}", "value": v, "fixed": True}
                    for i, v in enumerate(self.fixed_items)]
        return []

    @property
    def _next_id(self) -> int:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored.get("next_id", 0)
        if self.fixed_items:
            return len(self.fixed_items)
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
        return self._base_state() | {
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
        editable = [i for i in self.items if not i.get("fixed")]
        editable_ids = " | ".join(i["id"] for i in editable) if editable else ""

        affordances.append(AddItemAffordance(
            label="+ Add",
            method="POST",
            url=self.url,
            body={"action": "add", "value": "<item text>"},
            instruction=f"Add a new item to the {self.label} list.",
        ))

        if editable:
            affordances.append(Affordance(
                label="Edit Item",
                method="POST",
                url=self.url,
                body={"action": "edit", "id": f"<{editable_ids}>", "value": "<new value>"},
                instruction="Edit an existing item by ID.",
            ))

            affordances.append(Affordance(
                label="Remove Item",
                method="POST",
                url=self.url,
                body={"action": "remove", "id": f"<{editable_ids}>"},
                instruction="Remove an item by ID.",
            ))

        if len(self.items) > 1:
            can_up = [item["id"] for i, item in enumerate(self.items) if i > 0]
            can_down = [item["id"] for i, item in enumerate(self.items) if i < len(self.items) - 1]
            if can_up:
                affordances.append(Affordance(
                    label="Move Up",
                    method="POST",
                    url=self.url,
                    body={"action": "move_up", "id": f"<{' | '.join(can_up)}>"},
                    instruction="Move an item up one position.",
                ))
            if can_down:
                affordances.append(Affordance(
                    label="Move Down",
                    method="POST",
                    url=self.url,
                    body={"action": "move_down", "id": f"<{' | '.join(can_down)}>"},
                    instruction="Move an item down one position.",
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

        # Mark agent-only affordances as rendered (inline UI handles display)
        add_aff = None
        url = affs[0]["url"] if affs else ""
        endpoint = f'POST {url}'
        for aff in affs:
            action = aff.get("body", {}).get("action")
            if action in ("move_up", "move_down", "edit", "remove"):
                Eigenform.mark_rendered(aff)
            elif action == "add":
                add_aff = aff
                Eigenform.mark_rendered(aff)

        gap = '<span style="display: inline-block; width: 24px; height: 24px;"></span>'
        num_items = len(items)
        html += '<ol style="margin: 4px 0; padding-left: 24px;">'

        # Existing items
        for idx, item in enumerate(items):
            item_id = item["id"]
            item_val = escape(str(item.get("value", "")))
            is_fixed = item.get("fixed", False)
            html += f'<li style="margin: 4px 0; display: flex; align-items: center; gap: 4px;">'

            if is_fixed:
                # Fixed items: plain text, no edit/remove
                # Match input box: 200px width + 2*4px padding + 2*1px border = 210px total
                html += (
                    f'<span style="display: inline-block; width: 200px; padding: 2px 4px;'
                    f' border: 1px solid transparent; box-sizing: content-box;'
                    f' color: #555; background: #f0f0f0; border-radius: 3px;">{item_val}</span>'
                    f'{gap}'
                )
            else:
                # Editable items: input + confirm button
                edit_tooltip_js = (
                    f"this.nextElementSibling.title="
                    f"'{escape(endpoint)} '+JSON.stringify({{action:'edit',id:'{item_id}',value:this.value}})"
                )
                edit_default = {"action": "edit", "id": item_id, "value": item.get("value", "")}
                edit_tooltip = f'{escape(endpoint)} {escape(json.dumps(edit_default))}'
                html += (
                    f'<form style="display: inline; margin: 0;" onsubmit="fetch(\'{url}\','
                    f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                    f"body:JSON.stringify({{action:'edit',id:'{item_id}',value:this.elements.v.value}})"
                    f'}}).then(()=>location.reload()); return false">'
                    f'<input name="v" type="text" value="{item_val}"'
                    f' style="border: 1px solid #ddd; padding: 2px 4px; width: 200px;"'
                    f' oninput="{edit_tooltip_js}" />'
                    f' <button type="submit" style="{STYLE_CONFIRM}"'
                    f' title="{edit_tooltip}">&#10003;</button>'
                    f'</form>'
                )

            # Move up/down buttons inline (all items, fixed or not)
            for direction, arrow, can in [
                ("move_up", "&#9650;", idx > 0),
                ("move_down", "&#9660;", idx < num_items - 1),
            ]:
                if can:
                    html += render_inline_button(url, {"action": direction, "id": item_id}, arrow, STYLE_ARROW)
                else:
                    html += gap
            # Remove button (editable items only)
            if not is_fixed:
                html += render_inline_button(url, {"action": "remove", "id": item_id}, "x", STYLE_REMOVE)
            else:
                html += gap
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
                f' <button type="submit" style="{STYLE_CONFIRM}"'
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

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")
        items = [dict(i) for i in self.items]
        next_id = self._next_id
        item_ids = {i["id"] for i in items}

        if action == "add":
            value = body.get("value", "").strip()
            if not value:
                return self._error("Item value is required.", action=action)
            item_id = f"item_{next_id}"
            next_id += 1
            items.append({"id": item_id, "value": value})
            self._save(items, next_id)

        elif action == "edit":
            item_id = body.get("id", "")
            value = body.get("value", "")
            if item_id not in item_ids:
                return self._error(f"Unknown item: {item_id}. Valid: {', '.join(item_ids)}", action=action)
            target = next(i for i in items if i["id"] == item_id)
            if target.get("fixed"):
                return self._error(f"Item {item_id} is fixed and cannot be edited.", action=action)
            target["value"] = value
            self._save(items, next_id)

        elif action == "remove":
            item_id = body.get("id", "")
            if item_id not in item_ids:
                return self._error(f"Unknown item: {item_id}. Valid: {', '.join(item_ids)}", action=action)
            target = next(i for i in items if i["id"] == item_id)
            if target.get("fixed"):
                return self._error(f"Item {item_id} is fixed and cannot be removed.", action=action)
            items = [i for i in items if i["id"] != item_id]
            self._save(items, next_id)

        elif action in ("move", "move_up", "move_down"):
            item_id = body.get("id", "")
            if item_id not in item_ids:
                return self._error(f"Unknown item: {item_id}. Valid: {', '.join(item_ids)}", action=action)
            idx = next(i for i, it in enumerate(items) if it["id"] == item_id)
            if action == "move_up":
                position = idx - 1
            elif action == "move_down":
                position = idx + 1
            else:
                position = body.get("position")
                if isinstance(position, str) and position.isdigit():
                    position = int(position)
            if not isinstance(position, int) or position < 0 or position >= len(items):
                return self._error(f"Invalid position: {position}. Valid: 0 to {len(items) - 1}", action=action)
            item = items.pop(idx)
            items.insert(position, item)
            self._save(items, next_id)

        elif action == "na":
            self._store.set(self._scope, self.key, {"items": [], "next_id": next_id, "__na": True})

        elif action == "clear_na":
            self._store.set(self._scope, self.key, {"items": [], "next_id": next_id})

        else:
            return self._error(f"Unknown action: {action}", action=action)

        return self.serialize()
