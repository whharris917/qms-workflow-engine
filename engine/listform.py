"""ListForm — an ordered list of items with add/remove/reorder."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import (
    Affordance, AddConstraintAffordance, SimpleButtonAffordance,
    BUTTON_GAP, STYLE_CONFIRM, STYLE_REMOVE, STYLE_ARROW, render_inline_button,
)
from engine.eigenform import Eigenform
from engine.ordered_collection import OrderedCollection


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

    must_follow constrains item ordering by ID: {"item_2": ["item_0", "item_1"]}
    means item_2 must appear after item_0 and item_1. Moves that would violate
    a constraint are excluded from affordances and rejected by the handler.
    Constraints are ID-based (not value-based) so they survive renames.
    """
    fixed_items: list[str] = field(default_factory=list)
    must_follow: dict[str, list[str]] = field(default_factory=dict)
    allow_constraints: bool = True

    @property
    def _collection(self) -> OrderedCollection:
        oc = OrderedCollection(
            id_prefix="item",
            fixed_items=self.fixed_items,
            static_must_follow=self.must_follow,
            allow_constraints=self.allow_constraints,
        )
        oc.load(self.value)
        return oc

    @property
    def items(self) -> list[dict]:
        """List of items: [{"id": "item_0", "value": "...", "fixed": bool}, ...]"""
        return self._collection.items

    @property
    def na(self) -> bool:
        stored = self.value
        if stored and isinstance(stored, dict):
            return bool(stored.get("__na"))
        return False

    @property
    def is_complete(self) -> bool:
        return self.na or len(self.items) > 0

    def _serialize_state(self) -> dict:
        oc = self._collection
        state = self._base_state() | {
            "items": oc.items,
            "count": len(oc.items),
            "na": self.na,
        }
        mf = oc.effective_must_follow
        if mf:
            id_to_val = oc.id_to_value
            state["constraints"] = [
                {"item": item_id, "item_value": id_to_val.get(item_id, "?"),
                 "after": after_id, "after_value": id_to_val.get(after_id, "?")}
                for item_id, after_ids in mf.items()
                for after_id in after_ids
            ]
        return state

    def get_affordances(self) -> list[Affordance]:
        oc = self._collection

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
        items = oc.items
        editable = [i for i in items if not i.get("fixed")]
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

        if len(items) > 1:
            can_up = [items[i]["id"] for i in range(len(items)) if oc.can_move_up(i, items)]
            can_down = [items[i]["id"] for i in range(len(items)) if oc.can_move_down(i, items)]
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

        # Ordering constraint affordances
        if self.allow_constraints and len(items) > 1:
            item_ids = [i["id"] for i in items]
            item_labels = {i["id"]: i["value"] for i in items}
            id_labels = [f"{i['id']} ({i['value']})" for i in items]
            affordances.append(AddConstraintAffordance(
                label="Add Constraint",
                method="POST",
                url=self.url,
                body={"action": "add_constraint", "item": f"<{' | '.join(item_ids)}>", "after": f"<{' | '.join(item_ids)}>"},
                instruction=f"Require that <item> must always appear after <after>. Items: {', '.join(id_labels)}.",
                item_values=item_ids,
                item_labels=item_labels,
            ))
        dynamic = oc.stored_constraints
        if dynamic:
            pairs = " | ".join(f"{c['item']} after {c['after']}" for c in dynamic)
            affordances.append(Affordance(
                label="Remove Constraint",
                method="POST",
                url=self.url,
                body={"action": "remove_constraint", "item": f"<{pairs}>", "after": f"<see pairs>"},
                instruction=f"Remove a dynamic ordering constraint. Active: {pairs}.",
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
        oc = self._collection
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
            if action in ("move_up", "move_down", "edit", "remove",
                          "add_constraint", "remove_constraint"):
                Eigenform.mark_rendered(aff)
            elif action == "add":
                add_aff = aff
                Eigenform.mark_rendered(aff)

        gap = BUTTON_GAP
        num_items = len(items)
        html += '<ol style="margin: 4px 0; padding-left: 24px;">'

        # Fixed-width ID label style (consistent column width)
        id_style = ('display: inline-block; min-width: 52px; color: #666; text-align: center;'
                    ' background: #e8e8e8; border-radius: 10px; padding: 1px 6px;'
                    ' font-family: monospace; font-size: 0.85em;')

        # Build prerequisite lookup for inline display
        mf = oc.effective_must_follow
        id_to_val = oc.id_to_value
        static_pairs = {(item_id, after_id)
                        for item_id, after_ids in self.must_follow.items()
                        for after_id in after_ids}

        # Existing items
        for idx, item in enumerate(items):
            item_id = item["id"]
            item_val = escape(str(item.get("value", "")))
            is_fixed = item.get("fixed", False)
            html += f'<li style="margin: 4px 0; display: flex; align-items: center; gap: 4px;">'

            # Remove button (leftmost, editable items only)
            if not is_fixed:
                html += render_inline_button(url, {"action": "remove", "id": item_id}, "x", STYLE_REMOVE)
            else:
                html += gap

            # ID label
            html += f'<span style="{id_style}">{escape(item_id)}</span>'

            # Move up/down buttons
            for direction, arrow, can in [
                ("move_up", "&#9650;", oc.can_move_up(idx, items)),
                ("move_down", "&#9660;", oc.can_move_down(idx, items)),
            ]:
                if can:
                    html += render_inline_button(url, {"action": direction, "id": item_id}, arrow, STYLE_ARROW)
                else:
                    html += gap

            if is_fixed:
                html += (
                    f'<span style="display: inline-block; width: 200px; padding: 2px 4px;'
                    f' border: 1px solid transparent; box-sizing: content-box;'
                    f' color: #555; background: #f0f0f0; border-radius: 3px;">{item_val}</span>'
                    f'{gap}'
                )
            else:
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

            # Inline add-constraint dropdown + prerequisite labels with remove buttons
            prereqs = mf.get(item_id, [])
            if prereqs or (self.allow_constraints and num_items > 1):
                html += '<span style="color: #999; display: inline-flex; align-items: center; gap: 2px;">'
                if self.allow_constraints:
                    available = [i for i in items if i["id"] != item_id and i["id"] not in prereqs]
                    if available:
                        add_opts = "".join(
                            f'<option value="{escape(i["id"])}">{escape(i["value"])} ({escape(i["id"])})</option>'
                            for i in available
                        )
                        html += (
                            f'<select style="width: 110px;" onchange="'
                            f"if(this.value)fetch('{url}',"
                            f"{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                            f"body:JSON.stringify({{action:'add_constraint',item:'{item_id}',after:this.value}})"
                            f"}}).then(()=>location.reload())"
                            f'">'
                            f'<option value="">+ Prerequisite</option>'
                            f'{add_opts}'
                            f'</select>'
                        )
                if prereqs:
                    html += '<span style="font-style: italic;">after</span>'
                    for p_id in prereqs:
                        p_name = escape(id_to_val.get(p_id, p_id))
                        is_static = (item_id, p_id) in static_pairs
                        html += f'<span style="background: #f0f0f0; padding: 0 4px; border-radius: 2px;">{p_name}</span>'
                        if not is_static:
                            html += render_inline_button(
                                url, {"action": "remove_constraint", "item": item_id, "after": p_id},
                                "x", STYLE_REMOVE,
                            )
                html += '</span>'
            html += '</li>'

        # Add row
        if add_aff:
            add_default = {"action": "add", "value": ""}
            add_tooltip = f'{escape(endpoint)} {escape(json.dumps(add_default))}'
            add_tooltip_js = (
                f"this.nextElementSibling.title="
                f"'{escape(endpoint)} '+JSON.stringify({{action:'add',value:this.value}})"
            )
            html += (
                f'<li style="margin: 4px 0; display: flex; align-items: center; gap: 4px; list-style: none;">'
                f'{gap}'
                f'<span style="{id_style} visibility: hidden;">item_0</span>'
                f'{gap}{gap}'
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

        # Bottom controls
        html += '<div style="margin-top: 8px;">'
        for aff in affs:
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'

        return html

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")
        oc = self._collection

        if action == "add":
            value = body.get("value", "").strip()
            if not value:
                return self._error("Item value is required.", action=action)
            try:
                state = oc.add(value)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._store.set(self._scope, self.key, state)

        elif action == "edit":
            item_id = body.get("id", "")
            value = body.get("value", "")
            try:
                state = oc.edit(item_id, value)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._store.set(self._scope, self.key, state)

        elif action == "remove":
            item_id = body.get("id", "")
            try:
                state = oc.remove(item_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._store.set(self._scope, self.key, state)

        elif action in ("move", "move_up", "move_down"):
            item_id = body.get("id", "")
            try:
                if action == "move_up":
                    state = oc.move_up(item_id)
                elif action == "move_down":
                    state = oc.move_down(item_id)
                else:
                    position = body.get("position")
                    if isinstance(position, str) and position.isdigit():
                        position = int(position)
                    state = oc.move_to(item_id, position)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._store.set(self._scope, self.key, state)

        elif action == "add_constraint":
            item_id = body.get("item", "")
            after_id = body.get("after", "")
            try:
                state = oc.add_constraint(item_id, after_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._store.set(self._scope, self.key, state)

        elif action == "remove_constraint":
            item_id = body.get("item", "")
            after_id = body.get("after", "")
            try:
                state = oc.remove_constraint(item_id, after_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._store.set(self._scope, self.key, state)

        elif action == "na":
            self._store.set(self._scope, self.key, {"items": [], "next_id": oc.next_id, "__na": True})

        elif action == "clear_na":
            self._store.set(self._scope, self.key, {"items": [], "next_id": oc.next_id})

        else:
            return self._error(f"Unknown action: {action}", action=action)

        return self.serialize()
