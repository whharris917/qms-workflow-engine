"""RankForm — rank a fixed set of items by reordering."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from engine.affordances import Affordance, SimpleButtonAffordance, STYLE_ARROW, render_inline_button
from engine.eigenform import Eigenform


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
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        items = data.get("items", [])
        affs = data.get("affordances", [])

        # Mark condensed move affordances as rendered (arrows are built inline)
        for aff in affs:
            if aff.get("body", {}).get("action") in ("move_up", "move_down"):
                Eigenform.mark_rendered(aff)

        url = self.url
        num_items = len(items)

        html += '<ol style="margin: 4px 0; padding-left: 24px;">'
        for idx, item in enumerate(items):
            html += f'<li style="padding: 2px 0;">{escape(item)} '
            for direction, arrow, can in [
                ("move_up", "&#9650;", idx > 0),
                ("move_down", "&#9660;", idx < num_items - 1),
            ]:
                if can:
                    html += render_inline_button(url, {"action": direction, "item": item}, arrow, STYLE_ARROW)
            html += '</li>'
        html += '</ol>'

        # Render remaining affordances (Done button)
        for aff in affs:
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)

        return html

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
