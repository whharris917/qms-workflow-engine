"""RankForm — rank a fixed set of items by reordering."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.eigenforms import Eigenform


class SetRankAffordance(Affordance):
    """An affordance to submit the full ordering at once (for agents)."""

    def _render_hints(self) -> dict:
        return {"type": "button"}


@dataclass
class RankForm(Eigenform):
    """Rank a fixed set of items by reordering them."""
    items: list[str] = field(default_factory=list)

    @property
    def current_order(self) -> list[str]:
        stored = self.value
        if stored and isinstance(stored, list) and set(stored) == set(self.items):
            return stored
        return list(self.items)

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "items": self.current_order,
            "ranked": self.value is not None,
        }

    def get_affordances(self) -> list[Affordance]:
        order = self.current_order
        affordances: list[Affordance] = []
        for i, item in enumerate(order):
            if i > 0:
                affordances.append(SimpleButtonAffordance(
                    label=f"Up",
                    method="POST",
                    url=self.url,
                    body={"action": "move_up", "item": item},
                    instruction=f"Move '{item}' up one position.",
                ))
            if i < len(order) - 1:
                affordances.append(SimpleButtonAffordance(
                    label=f"Down",
                    method="POST",
                    url=self.url,
                    body={"action": "move_down", "item": item},
                    instruction=f"Move '{item}' down one position.",
                ))
        items_str = ", ".join(f'"{item}"' for item in self.items)
        affordances.append(SetRankAffordance(
            label="Set Order",
            method="POST",
            url=self.url,
            body={"action": "set_order", "order": f"<[{items_str}]>"},
            instruction=f"Submit the full ordering as a JSON array. Must be a permutation of the items.",
        ))
        return affordances

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        items = data.get("items", [])
        affs = data.get("affordances", [])

        html += '<ol style="margin: 4px 0; padding-left: 24px;">'
        for item in items:
            html += f'<li style="padding: 2px 0;">{escape(item)} '
            # Find move affordances for this item
            for aff in affs:
                body = aff.get("body", {})
                if body.get("item") == item and body.get("action") in ("move_up", "move_down"):
                    arrow = "&#9650;" if body["action"] == "move_up" else "&#9660;"
                    Eigenform.mark_rendered(aff)
                    body_js = json.dumps(body).replace('"', '&quot;')
                    html += (
                        f'<button onclick="fetch(\'{aff["url"]}\','
                        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                        f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
                        f' style="cursor: pointer; font-size: 11px; width: 24px; height: 24px; margin: 0 1px;"'
                        f' title="{escape(aff.get("instruction", ""))}">'
                        f'{arrow}</button>'
                    )
            html += '</li>'
        html += '</ol>'

        # Render remaining affordances (Set Order button)
        for aff in affs:
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)

        return html

    def _handle(self, body: dict) -> dict:
        action = body.get("action")
        order = self.current_order

        if action == "move_up":
            item = body.get("item")
            if item in order:
                idx = order.index(item)
                if idx > 0:
                    order[idx], order[idx - 1] = order[idx - 1], order[idx]
            self._store.set(self._scope, self.key, order)
            return self.serialize()

        elif action == "move_down":
            item = body.get("item")
            if item in order:
                idx = order.index(item)
                if idx < len(order) - 1:
                    order[idx], order[idx + 1] = order[idx + 1], order[idx]
            self._store.set(self._scope, self.key, order)
            return self.serialize()

        elif action == "set_order":
            new_order = body.get("order")
            if isinstance(new_order, list) and set(new_order) == set(self.items):
                self._store.set(self._scope, self.key, new_order)
                return self.serialize()
            result = self.serialize()
            result["error"] = f"Order must be a permutation of {self.items}"
            result["failed_action"] = body
            return result

        result = self.serialize()
        result["error"] = f"Unknown action: {action}"
        result["failed_action"] = body
        return result
