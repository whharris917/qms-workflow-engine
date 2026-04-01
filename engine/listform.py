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
    def _effective_allow_constraints(self) -> bool:
        """allow_constraints from store override if set, else Python default."""
        if self._store is not None:
            override = self._store.get(self._scope, f"{self.key}.__config")
            if override is not None:
                return override.get("allow_constraints", self.allow_constraints)
        return self.allow_constraints

    def _snapshot_edit_state(self) -> dict:
        state = super()._snapshot_edit_state()
        state["__config"] = self._store.get(self._scope, f"{self.key}.__config")
        state["__value"] = self._store.get(self._scope, self.key)
        return state

    def _restore_edit_state(self, state: dict):
        super()._restore_edit_state(state)
        self._store.set(self._scope, f"{self.key}.__config", state.get("__config"))
        self._store.set(self._scope, self.key, state.get("__value"))

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        item_ids = [i["id"] for i in self.items]
        if item_ids:
            ids_str = " | ".join(item_ids)
            affs.append(Affordance(
                label="Toggle Fixed", method="POST", url=self.url,
                body={"action": "toggle_fixed", "id": f"<{ids_str}>"},
                instruction="Toggle whether an item is fixed (immutable in execution mode).",
            ))
        affs.append(Affordance(
            label="Toggle Constraints", method="POST", url=self.url,
            body={"action": "toggle_constraints"},
            instruction=f"Toggle whether ordering constraints are allowed. Currently: {self._effective_allow_constraints}",
        ))
        return affs

    @property
    def _collection(self) -> OrderedCollection:
        oc = OrderedCollection(
            id_prefix="item",
            fixed_items=self.fixed_items,
            static_must_follow=self.must_follow,
            allow_constraints=self._effective_allow_constraints,
            relax_fixed=self.edit_mode,
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
        editable = items if self.edit_mode else [i for i in items if not i.get("fixed")]
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
        if self._effective_allow_constraints and len(items) > 1:
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

    def _render_edit_header(self, data: dict) -> str:
        """Render editable label, instruction, and config controls."""
        url = self.url
        label = data["label"]
        instruction = data.get("instruction") or ""

        # Label
        label_body = json.dumps({"action": "set_label", "label": label})
        label_tooltip = f'POST {url} {escape(label_body)}'
        html = (
            f'<form style="display: flex; align-items: center; gap: 4px;'
            f' margin: 0.83em 0;" onsubmit="fetch(\'{url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{action:\'set_label\',label:this.elements.v.value}})'
            f'}}).then(()=>location.reload()); return false">'
            f'<input name="v" type="text" value="{escape(label)}"'
            f' style="font: inherit; font-size: 1.17em; font-weight: bold;'
            f' border: 1px solid #ddd; padding: 1px 3px; margin: 0;"'
            f' title="{label_tooltip}" />'
            f' <button type="submit" style="{STYLE_CONFIRM}"'
            f' title="{label_tooltip}">&#10003;</button>'
            f'</form>'
        )

        # Instruction
        instr_body = json.dumps({"action": "set_instruction", "instruction": instruction})
        instr_tooltip = f'POST {url} {escape(instr_body)}'
        html += (
            f'<form style="display: flex; align-items: center; gap: 4px;'
            f' margin: 1em 0;" onsubmit="fetch(\'{url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{action:\'set_instruction\',instruction:this.elements.v.value}})'
            f'}}).then(()=>location.reload()); return false">'
            f'<input name="v" type="text" value="{escape(instruction)}"'
            f' placeholder="Instruction text"'
            f' style="font: inherit; border: 1px solid #ddd; padding: 1px 3px;'
            f' margin: 0; width: 100%;"'
            f' title="{instr_tooltip}" />'
            f' <button type="submit" style="{STYLE_CONFIRM}"'
            f' title="{instr_tooltip}">&#10003;</button>'
            f'</form>'
        )

        # Allow constraints toggle
        ac = self._effective_allow_constraints
        ac_body = json.dumps({"action": "toggle_constraints"})
        ac_tooltip = f'POST {url} {escape(ac_body)}'
        ac_bg = "#efffef" if ac else "#f8f8f8"
        ac_border = "#4a4" if ac else "#ccc"
        html += (
            f'<div style="margin: 4px 0; font-size: 0.9em; color: #666;">'
            f'<button onclick="fetch(\'{url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({ac_body.replace(chr(34), "&quot;")})}}).then(()=>location.reload())"'
            f' style="cursor: pointer; font: inherit; font-size: 0.9em; border: 1px solid {ac_border};'
            f' background: {ac_bg}; padding: 1px 8px; border-radius: 3px;"'
            f' title="{ac_tooltip}">constraints: {"on" if ac else "off"}</button>'
            f'</div>'
        )

        # Mark edit-specific affordances as rendered
        for aff in data.get("affordances", []):
            action = aff.get("body", {}).get("action")
            if action in ("set_label", "set_instruction", "toggle_constraints"):
                Eigenform.mark_rendered(aff)

        return html

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        oc = self._collection

        if data.get("edit_mode"):
            html = self._render_edit_header(data)
        else:
            html = f'<h3>{escape(data["label"])}</h3>'
            if data.get("instruction"):
                html += f'<p>{escape(data["instruction"])}</p>'

        affs = data.get("affordances", [])

        if data.get("na"):
            html += '<p style="color: #888; font-style: italic;">N/A</p>'
            for aff in affs:
                if not aff.get("_rendered"):
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
                          "add_constraint", "remove_constraint",
                          "toggle_fixed", "toggle_constraint_fixed"):
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
            is_fixed = item.get("fixed", False) and not data.get("edit_mode")
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

            is_item_fixed = item.get("fixed", False)
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

            # Fixed toggle (edit mode only) — pin icon
            if data.get("edit_mode"):
                pin_color = "#856404" if is_item_fixed else "#ccc"
                pin_bg = "#fff3cd" if is_item_fixed else "none"
                pin_label = "fixed" if is_item_fixed else "unfixed"
                html += render_inline_button(
                    url, {"action": "toggle_fixed", "id": item_id},
                    f'<span style="font-size: 14px;">&#128204;</span>',
                    f'cursor: pointer; border: 1px solid {pin_color}; background: {pin_bg};'
                    f' width: 24px; height: 24px; font-size: 10px; padding: 0;'
                    f' vertical-align: middle; box-sizing: content-box;',
                )

            # Inline add-constraint dropdown + prerequisite pills with remove buttons
            prereqs = mf.get(item_id, [])
            if prereqs or (self._effective_allow_constraints and num_items > 1):
                html += '<span style="color: #999; display: inline-flex; align-items: center; gap: 2px;">'
                if self._effective_allow_constraints:
                    available = [i for i in items if i["id"] != item_id and i["id"] not in prereqs]
                    if available:
                        def _opt(i: dict) -> str:
                            body = json.dumps({"action": "add_constraint", "item": item_id, "after": i["id"]})
                            label = i["value"] + " (" + i["id"] + ")" if i["value"] else i["id"]
                            return (
                                f'<option value="{escape(i["id"])}"'
                                f' title="POST {url} {escape(body)}">'
                                f'{escape(label)}</option>'
                            )
                        add_opts = "".join(_opt(i) for i in available)
                        html += (
                            f'<span style="position: relative; display: inline-block;'
                            f' width: 24px; height: 24px; box-sizing: content-box;'
                            f' border: 1px solid #ccc; background: #f8f8f8; vertical-align: middle;">'
                            f'<span style="position: absolute; inset: 0; display: flex;'
                            f' align-items: center; justify-content: center;'
                            f' font-size: 18px; font-weight: normal; pointer-events: none;">&#9745;</span>'
                            f'<select title="POST {url} {{&quot;action&quot;:&quot;add_constraint&quot;,&quot;item&quot;:&quot;{item_id}&quot;,&quot;after&quot;:&quot;...&quot;}}"'
                            f' style="position: absolute; inset: 0; width: 100%; height: 100%;'
                            f' opacity: 0; cursor: pointer;" onchange="'
                            f"if(this.value)fetch('{url}',"
                            f"{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                            f"body:JSON.stringify({{action:'add_constraint',item:'{item_id}',after:this.value}})"
                            f"}}).then(()=>location.reload())"
                            f'">'
                            f'<option value="">&#8212;</option>'
                            f'{add_opts}'
                            f'</select>'
                            f'</span>'
                        )
                if prereqs:
                    in_edit = data.get("edit_mode", False)
                    stored_cs = oc.stored_constraints
                    for p_id in prereqs:
                        p_name = escape(id_to_val.get(p_id, p_id) or p_id)
                        is_static = (item_id, p_id) in static_pairs
                        # Check if a stored entry overrides this constraint's fixed state
                        stored_c = next((c for c in stored_cs
                                         if c["item"] == item_id and c["after"] == p_id), None)
                        is_effectively_fixed = is_static and (not stored_c or stored_c.get("fixed") is not False)
                        if not is_static and stored_c:
                            is_effectively_fixed = bool(stored_c.get("fixed"))
                        pill_bg = "#fff3cd" if is_effectively_fixed else "#e8e8e8"
                        pill_border = "1px solid #856404" if is_effectively_fixed else "none"
                        html += (
                            f'<span style="display: inline-block; min-width: 52px; color: #666;'
                            f' text-align: center; background: {pill_bg}; border: {pill_border}; border-radius: 10px;'
                            f' padding: 1px 6px; font-family: monospace; font-size: 0.85em;">'
                            f'{p_name}</span>'
                        )
                        if in_edit:
                            # Pin/unpin toggle for constraint
                            pin_icon = "&#128204;" if is_effectively_fixed else "&#128204;"
                            pin_style = (
                                f'cursor: pointer; border: 1px solid {"#856404" if is_effectively_fixed else "#ccc"};'
                                f' background: {"#fff3cd" if is_effectively_fixed else "none"};'
                                f' width: 18px; height: 18px; font-size: 10px; padding: 0;'
                                f' vertical-align: middle; box-sizing: content-box;'
                            )
                            html += render_inline_button(
                                url, {"action": "toggle_constraint_fixed", "item": item_id, "after": p_id},
                                f'<span style="font-size: 11px;">{pin_icon}</span>', pin_style,
                            )
                            # Remove button (available for all constraints in edit mode)
                            html += render_inline_button(
                                url, {"action": "remove_constraint", "item": item_id, "after": p_id},
                                "x", STYLE_REMOVE,
                            )
                        elif not is_static:
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

        if action == "toggle_constraints" and self.editable and self.edit_mode:
            self._push_undo()
            cfg = self._store.get(self._scope, f"{self.key}.__config") or {}
            cfg["allow_constraints"] = not self._effective_allow_constraints
            self._store.set(self._scope, f"{self.key}.__config", cfg)
            return self.serialize()

        # Edit-mode only actions
        if action == "toggle_fixed" and self.editable and self.edit_mode:
            self._push_undo()
            item_id = body.get("id", "")
            item = next((i for i in self._collection.items if i["id"] == item_id), None)
            if not item:
                return self._error(f"Unknown item: {item_id}", action=action)
            oc = self._collection
            state = oc.set_fixed(item_id, not item.get("fixed", False))
            self._store.set(self._scope, self.key, state)
            return self.serialize()

        if action == "toggle_constraint_fixed" and self.editable and self.edit_mode:
            self._push_undo()
            item_id = body.get("item", "")
            after_id = body.get("after", "")
            # Determine current fixed state
            is_static = after_id in self.must_follow.get(item_id, [])
            stored = next((c for c in self._collection.stored_constraints
                           if c["item"] == item_id and c["after"] == after_id), None)
            currently_fixed = is_static and (not stored or stored.get("fixed") is not False)
            if not is_static and stored:
                currently_fixed = bool(stored.get("fixed"))
            oc = self._collection
            try:
                state = oc.set_constraint_fixed(item_id, after_id, not currently_fixed)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._store.set(self._scope, self.key, state)
            return self.serialize()

        # Push undo before any item mutation in edit mode
        if self.edit_mode and action in ("add", "edit", "remove", "move", "move_up", "move_down",
                                          "add_constraint", "remove_constraint", "na", "clear_na"):
            self._push_undo()

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
