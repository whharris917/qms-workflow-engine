"""RankForm — rank a fixed set of items by reordering."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.eigenform import Eigenform
from engine.templates import render_template


@dataclass
class RankForm(Eigenform):
    """Rank a fixed set of items by reordering them.

    Requires explicit confirmation via "Done" to be considered complete.
    This prevents premature auto-advance in ChainForm when the user
    has only moved one item but intends to make more adjustments.
    """
    items: list[str] = field(default_factory=list)

    @property
    def _state(self) -> dict:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored
        return {}

    @property
    def current_order(self) -> list[str]:
        order = self._state.get("order")
        if order and isinstance(order, list) and set(order) == set(self.items):
            return order
        return list(self.items)

    @property
    def confirmed(self) -> bool:
        return bool(self._state.get("__confirmed"))

    @property
    def is_complete(self) -> bool:
        return self.confirmed

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "items": self.current_order,
            "confirmed": self.confirmed,
        }

    def _save(self, order: list[str], confirmed: bool):
        self._store.set(self._scope, self.key, {
            "order": order,
            "__confirmed": confirmed,
        })

    def get_affordances(self) -> list[Affordance]:
        from engine.affordances import Affordance as BaseAffordance
        order = self.current_order
        affordances: list[Affordance] = []
        if len(order) > 1:
            can_up = [item for i, item in enumerate(order) if i > 0]
            can_down = [item for i, item in enumerate(order) if i < len(order) - 1]
            if can_up:
                affordances.append(BaseAffordance(
                    label="Move Up",
                    method="POST",
                    url=self.url,
                    body={"action": "move_up", "item": f"<{' | '.join(can_up)}>"},
                    instruction="Move an item up one position.",
                ))
            if can_down:
                affordances.append(BaseAffordance(
                    label="Move Down",
                    method="POST",
                    url=self.url,
                    body={"action": "move_down", "item": f"<{' | '.join(can_down)}>"},
                    instruction="Move an item down one position.",
                ))
        if not self.confirmed:
            affordances.append(SimpleButtonAffordance(
                label="Done",
                method="POST",
                url=self.url,
                body={"action": "done"},
                instruction="Confirm the current ordering.",
            ))
        return affordances

    def render_from_data(self, data: dict) -> str:
        return render_template("rank.html", data=data, ef=self,
                               url=self.url)

    def _handle(self, body: dict) -> dict:
        action = body.get("action")
        order = self.current_order

        if action == "done":
            self._save(order, confirmed=True)
            return self.serialize()

        elif action == "move_up":
            item = body.get("item")
            if item in order:
                idx = order.index(item)
                if idx > 0:
                    order[idx], order[idx - 1] = order[idx - 1], order[idx]
            self._save(order, confirmed=False)
            return self.serialize()

        elif action == "move_down":
            item = body.get("item")
            if item in order:
                idx = order.index(item)
                if idx < len(order) - 1:
                    order[idx], order[idx + 1] = order[idx + 1], order[idx]
            self._save(order, confirmed=False)
            return self.serialize()

        return self._error(f"Unknown action: {action}", body=body)
