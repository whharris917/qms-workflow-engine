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


class AddConstraintAffordance(Affordance):
    """An affordance that adds an ordering constraint between two items."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None, item_values: list[str] | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.item_values = item_values or []

    def _render_hints(self) -> dict:
        return {"type": "constraint_picker", "options": self.item_values}


@dataclass
class ListForm(Eigenform):
    """An ordered list of string items with add, remove, edit, and reorder.

    If fixed_items is provided, those items are seeded into the list on
    first access and cannot be removed or renamed. They can be freely
    reordered alongside user-added items.

    must_follow constrains item ordering: {"C": ["A", "B"]} means the
    item with value "C" must appear after items "A" and "B". Moves that
    would violate a constraint are excluded from affordances and rejected
    by the handler. Constraints apply to both fixed and user-added items.
    """
    fixed_items: list[str] = field(default_factory=list)
    must_follow: dict[str, list[str]] = field(default_factory=dict)
    allow_constraints: bool = True

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
    def _stored_constraints(self) -> list[dict]:
        """Dynamic constraints from the store: [{"item": "X", "after": "Y"}, ...]"""
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored.get("constraints", [])
        return []

    @property
    def _effective_must_follow(self) -> dict[str, list[str]]:
        """Merge static must_follow with dynamic stored constraints."""
        result = {k: list(v) for k, v in self.must_follow.items()}
        for c in self._stored_constraints:
            result.setdefault(c["item"], [])
            if c["after"] not in result[c["item"]]:
                result[c["item"]].append(c["after"])
        return result

    @property
    def na(self) -> bool:
        stored = self.value
        if stored and isinstance(stored, dict):
            return bool(stored.get("__na"))
        return False

    @property
    def is_complete(self) -> bool:
        return self.na or len(self.items) > 0

    def _save(self, items: list[dict], next_id: int | None = None,
              constraints: list[dict] | None = None):
        state = {
            "items": items,
            "next_id": next_id if next_id is not None else self._next_id,
        }
        saved_constraints = constraints if constraints is not None else self._stored_constraints
        if saved_constraints:
            state["constraints"] = saved_constraints
        self._store.set(self._scope, self.key, state)

    def _can_move_up(self, idx: int, items: list[dict]) -> bool:
        """Check if moving item at idx up one position respects constraints."""
        if idx <= 0:
            return False
        mf = self._effective_must_follow
        moved_val = items[idx]["value"]
        displaced_val = items[idx - 1]["value"]
        # Moving up means the moved item would now be before the displaced item.
        # Violation if the moved item must follow the displaced item.
        if displaced_val in mf.get(moved_val, []):
            return False
        return True

    def _can_move_down(self, idx: int, items: list[dict]) -> bool:
        """Check if moving item at idx down one position respects constraints."""
        if idx >= len(items) - 1:
            return False
        mf = self._effective_must_follow
        moved_val = items[idx]["value"]
        displaced_val = items[idx + 1]["value"]
        # Moving down means the displaced item would now be before the moved item.
        # Violation if the displaced item must follow the moved item.
        if moved_val in mf.get(displaced_val, []):
            return False
        return True

    def _would_create_cycle(self, item_val: str, after_val: str,
                            mf: dict[str, list[str]]) -> bool:
        """Check if adding 'item must follow after' would create a cycle.

        Walks from after_val through its prerequisites (must_follow chains).
        If item_val is reachable, then after_val transitively depends on
        item_val, and adding 'item must follow after' closes a cycle.
        """
        visited = set()
        stack = [after_val]
        while stack:
            current = stack.pop()
            if current == item_val:
                return True
            if current in visited:
                continue
            visited.add(current)
            stack.extend(mf.get(current, []))
        return False

    def _enforce_constraints(self, items: list[dict]) -> list[dict]:
        """Reorder items to satisfy all constraints, preserving relative order.

        Uses a stable topological sort: items are placed in their original
        order as long as all prerequisites have already been placed.
        Deferred items are placed as soon as their prerequisites appear.
        Acyclicity is guaranteed by cycle detection in add_constraint.
        """
        mf = self._effective_must_follow
        if not mf:
            return items
        result = []
        deferred = []
        placed = set()
        for item in items:
            prereqs = set(mf.get(item["value"], []))
            if prereqs <= placed:
                result.append(item)
                placed.add(item["value"])
                # Flush deferred items whose prerequisites are now met
                changed = True
                while changed:
                    changed = False
                    still_deferred = []
                    for d in deferred:
                        if set(mf.get(d["value"], [])) <= placed:
                            result.append(d)
                            placed.add(d["value"])
                            changed = True
                        else:
                            still_deferred.append(d)
                    deferred = still_deferred
            else:
                deferred.append(item)
        result.extend(deferred)
        return result

    def _serialize_state(self) -> dict:
        state = self._base_state() | {
            "items": self.items,
            "count": len(self.items),
            "na": self.na,
        }
        mf = self._effective_must_follow
        if mf:
            state["constraints"] = [
                {"item": item, "after": after}
                for item, afters in mf.items()
                for after in afters
            ]
        return state

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
            items = self.items
            can_up = [items[i]["id"] for i in range(len(items)) if self._can_move_up(i, items)]
            can_down = [items[i]["id"] for i in range(len(items)) if self._can_move_down(i, items)]
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
        if self.allow_constraints and len(self.items) > 1:
            item_vals = [i["value"] for i in self.items]
            affordances.append(AddConstraintAffordance(
                label="Add Constraint",
                method="POST",
                url=self.url,
                body={"action": "add_constraint", "item": f"<{' | '.join(item_vals)}>", "after": f"<{' | '.join(item_vals)}>"},
                instruction="Require that <item> must always appear after <after> in the list.",
                item_values=item_vals,
            ))
        dynamic = self._stored_constraints
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
                ("move_up", "&#9650;", self._can_move_up(idx, items)),
                ("move_down", "&#9660;", self._can_move_down(idx, items)),
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

        # Constraints display
        constraints = data.get("constraints", [])
        if constraints:
            # Determine which are static (from must_follow) vs dynamic (removable)
            static_pairs = {(item, after)
                            for item, afters in self.must_follow.items()
                            for after in afters}
            html += '<div style="margin-top: 6px; font-size: 0.9em; color: #666;">'
            html += '<strong>Ordering constraints:</strong>'
            for c in constraints:
                pair = (c["item"], c["after"])
                is_static = pair in static_pairs
                html += (
                    f'<div style="margin: 2px 0; padding: 2px 4px; display: flex; align-items: center; gap: 4px;">'
                    f'<span>{escape(c["item"])} must follow {escape(c["after"])}</span>'
                )
                if is_static:
                    html += '<span style="font-size: 0.85em; color: #999;">(built-in)</span>'
                else:
                    html += render_inline_button(
                        url, {"action": "remove_constraint", "item": c["item"], "after": c["after"]},
                        "x", STYLE_REMOVE,
                    )
                html += '</div>'
            html += '</div>'
        # Mark remove_constraint as rendered (inline buttons handle it)
        for aff in affs:
            if aff.get("body", {}).get("action") == "remove_constraint":
                Eigenform.mark_rendered(aff)

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
            removed_val = target["value"]
            items = [i for i in items if i["id"] != item_id]
            # Remove dynamic constraints referencing the removed item
            constraints = [c for c in self._stored_constraints
                           if c["item"] != removed_val and c["after"] != removed_val]
            self._save(items, next_id, constraints=constraints)

        elif action in ("move", "move_up", "move_down"):
            item_id = body.get("id", "")
            if item_id not in item_ids:
                return self._error(f"Unknown item: {item_id}. Valid: {', '.join(item_ids)}", action=action)
            idx = next(i for i, it in enumerate(items) if it["id"] == item_id)
            if action == "move_up":
                if not self._can_move_up(idx, items):
                    return self._error(f"Cannot move {item_id} up: ordering constraint.", action=action)
                position = idx - 1
            elif action == "move_down":
                if not self._can_move_down(idx, items):
                    return self._error(f"Cannot move {item_id} down: ordering constraint.", action=action)
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

        elif action == "add_constraint":
            if not self.allow_constraints:
                return self._error("Ordering constraints are not allowed on this list.", action=action)
            item_val = body.get("item", "")
            after_val = body.get("after", "")
            item_values = {i["value"] for i in items}
            if item_val not in item_values:
                return self._error(f"Unknown item value: {item_val!r}.", action=action)
            if after_val not in item_values:
                return self._error(f"Unknown item value: {after_val!r}.", action=action)
            if item_val == after_val:
                return self._error("An item cannot be constrained to follow itself.", action=action)
            # Check for duplicate (including static constraints)
            mf = self._effective_must_follow
            if after_val in mf.get(item_val, []):
                return self._error(f"Constraint already exists: {item_val!r} must follow {after_val!r}.", action=action)
            # Check it wouldn't create a cycle (transitive)
            if self._would_create_cycle(item_val, after_val, mf):
                return self._error(f"Would create a cycle: {after_val!r} transitively depends on {item_val!r}.", action=action)
            constraints = list(self._stored_constraints) + [{"item": item_val, "after": after_val}]
            self._save(items, next_id, constraints=constraints)
            # Re-read and enforce all constraints (new constraint may require cascading moves)
            items = [dict(i) for i in self.items]
            items = self._enforce_constraints(items)
            self._save(items, next_id, constraints=constraints)

        elif action == "remove_constraint":
            item_val = body.get("item", "")
            after_val = body.get("after", "")
            # Can only remove dynamic constraints, not static must_follow
            constraints = self._stored_constraints
            new_constraints = [c for c in constraints
                               if not (c["item"] == item_val and c["after"] == after_val)]
            if len(new_constraints) == len(constraints):
                return self._error(f"No dynamic constraint: {item_val!r} after {after_val!r}.", action=action)
            self._save(items, next_id, constraints=new_constraints)

        elif action == "na":
            self._store.set(self._scope, self.key, {"items": [], "next_id": next_id, "__na": True})

        elif action == "clear_na":
            self._store.set(self._scope, self.key, {"items": [], "next_id": next_id})

        else:
            return self._error(f"Unknown action: {action}", action=action)

        return self.serialize()
