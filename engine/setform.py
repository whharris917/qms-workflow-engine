"""SetForm — an unordered collection of unique items."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.component import Component
from engine.templates import render_template


class AddToSetAffordance(Affordance):
    """An affordance that adds an item to the set."""

    def _render_hints(self) -> dict:
        return {"type": "text_input_add", "placeholder": "New item"}


@dataclass
class SetForm(Component):
    """An unordered collection of unique string items.

    Unlike ListForm, items have no order, no stable IDs, and no
    duplicates. Adding an existing item is rejected. Removing is
    by value, not by ID.
    """
    form = "set"

    @property
    def items(self) -> list[str]:
        """Current items as a list (JSON has no set type)."""
        stored = self.value
        if stored and isinstance(stored, list):
            return stored
        return []

    @property
    def is_complete(self) -> bool:
        return len(self.items) > 0

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "items": self.items,
            "count": len(self.items),
        }

    def get_affordances(self) -> list[Affordance]:
        affordances: list[Affordance] = [
            AddToSetAffordance(
                label="+ Add",
                method="POST",
                url=self.url,
                body={"action": "add", "value": "<item>"},
                instruction=f"Add a unique item to the {self.label} set. Duplicates are rejected.",
            ),
        ]
        if self.items:
            items_str = " | ".join(self.items)
            affordances.append(Affordance(
                label="Remove",
                method="POST",
                url=self.url,
                body={"action": "remove", "value": f"<{items_str}>"},
                instruction="Remove an item by value.",
            ))
        return affordances

    def render_from_data(self, data: dict) -> str:
        return render_template("set.html", data=data, ef=self)

    _actions = {
        "add": "_do_add",
        "remove": "_do_remove",
    }

    def _do_add(self, body: dict) -> dict:
        items = list(self.items)
        value = body.get("value", "").strip()
        if not value:
            return self._error("Item value is required.", action="add")
        if value in items:
            return self._error(f"Duplicate: {value!r} is already in the set.", action="add")
        items.append(value)
        self._store.set(self._scope, self.key, items)
        return self.serialize()

    def _do_remove(self, body: dict) -> dict:
        items = list(self.items)
        value = body.get("value", "")
        if value not in items:
            return self._error(
                f"Not in set: {value!r}. Current items: {', '.join(items)}",
                action="remove",
            )
        items.remove(value)
        self._store.set(self._scope, self.key, items)
        return self.serialize()
