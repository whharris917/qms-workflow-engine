"""ListForm — an ordered list of items with add/remove/reorder."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.affordances import Affordance, AddConstraintAffordance, SimpleButtonAffordance
from engine.component import Component
from engine.ordered_collection import OrderedCollection
from engine.templates import render_template


class AddItemAffordance(Affordance):
    """An affordance that adds an item to the list."""

    def _render_hints(self) -> dict:
        return {"type": "text_input_add", "placeholder": "New item"}


@dataclass
class ListForm(Component):
    """An ordered list of string items with add, remove, edit, and reorder.

    If fixed_items is provided, those items are seeded into the list on
    first access and cannot be removed or renamed. They can be freely
    reordered alongside user-added items.

    must_follow constrains item ordering by ID: {"item_2": ["item_0", "item_1"]}
    means item_2 must appear after item_0 and item_1. Moves that would violate
    a constraint are excluded from affordances and rejected by the handler.
    Constraints are ID-based (not value-based) so they survive renames.
    """
    form = "list"

    fixed_items: list[str] = field(default_factory=list)
    must_follow: dict[str, list[str]] = field(default_factory=dict)
    allow_constraints: bool = True

    def _snapshot_edit_state(self) -> dict:
        state = super()._snapshot_edit_state()
        state["__value"] = self._store.get(self._scope, self.key)
        return state

    def _restore_edit_state(self, state: dict):
        super()._restore_edit_state(state)
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
            instruction=f"Toggle whether ordering constraints are allowed. Currently: {self.allow_constraints}",
        ))
        return affs

    @property
    def _collection(self) -> OrderedCollection:
        oc = OrderedCollection(
            id_prefix="item",
            fixed_items=self.fixed_items,
            static_must_follow=self.must_follow,
            allow_constraints=self.allow_constraints,
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
        all_mf = oc.all_must_follow
        if all_mf:
            eff_mf = oc.effective_must_follow
            id_to_val = oc.id_to_value
            state["constraints"] = [
                {"item": item_id, "item_value": id_to_val.get(item_id, "?"),
                 "after": after_id, "after_value": id_to_val.get(after_id, "?"),
                 **({} if after_id in eff_mf.get(item_id, []) else {"active": False})}
                for item_id, after_ids in all_mf.items()
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
        oc = self._collection
        static_pairs = {(item_id, after_id)
                        for item_id, after_ids in self.must_follow.items()
                        for after_id in after_ids}
        return render_template("list.html", data=data, ef=self,
                               url=self.url, label=data["label"],
                               instruction=data.get("instruction") or "",
                               oc=oc,
                               allow_constraints=self.allow_constraints,
                               all_must_follow=oc.all_must_follow,
                               id_to_val=oc.id_to_value,
                               static_pairs=static_pairs,
                               stored_constraints=oc.stored_constraints)

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")

        if action == "toggle_constraints" and self.editable and self.edit_mode:
            self._push_undo()
            self._set_my_config("allow_constraints", not self.allow_constraints)
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
