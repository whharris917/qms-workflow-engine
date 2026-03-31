"""SetForm — an unordered collection of unique items."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape

from engine.affordances import (
    Affordance, SimpleButtonAffordance,
    STYLE_REMOVE, render_inline_button,
)
from engine.bases import CollectionForm
from engine.eigenform import Eigenform


class AddToSetAffordance(Affordance):
    """An affordance that adds an item to the set."""

    def _render_hints(self) -> dict:
        return {"type": "text_input_add", "placeholder": "New item"}


@dataclass
class SetForm(CollectionForm):
    """An unordered collection of unique string items.

    Unlike ListForm, items have no order, no stable IDs, and no
    duplicates. Adding an existing item is rejected. Removing is
    by value, not by ID.
    """

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
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        affs = data.get("affordances", [])
        items = data.get("items", [])
        url = affs[0]["url"] if affs else ""
        endpoint = f'POST {url}'

        # Mark remove affordance as rendered (inline buttons handle it)
        add_aff = None
        for aff in affs:
            action = aff.get("body", {}).get("action")
            if action == "remove":
                Eigenform.mark_rendered(aff)
            elif action == "add":
                add_aff = aff
                Eigenform.mark_rendered(aff)

        # Items as pills with remove buttons
        if items:
            html += '<div style="display: flex; flex-direction: column; gap: 4px; margin: 6px 0;">'
            for item in items:
                html += (
                    f'<span style="display: inline-flex; align-items: center; gap: 4px; width: fit-content;">'
                )
                html += render_inline_button(
                    url, {"action": "remove", "value": item}, "x", STYLE_REMOVE,
                )
                html += (
                    f'<span style="background: #f0f0f0; padding: 2px 8px; border-radius: 3px;">'
                    f'{escape(item)}</span>'
                    f'</span>'
                )
            html += '</div>'
        else:
            html += '<p style="color: #888; font-style: italic;">Empty set.</p>'

        # Add input
        if add_aff:
            add_tooltip = f'{escape(endpoint)} {escape(json.dumps({"action": "add", "value": ""}))}'
            add_tooltip_js = (
                f"this.nextElementSibling.title="
                f"'{escape(endpoint)} '+JSON.stringify({{action:'add',value:this.value}})"
            )
            html += (
                f'<form style="display: inline; margin: 4px 0;" onsubmit="fetch(\'{url}\','
                f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f"body:JSON.stringify({{action:'add',value:this.elements.v.value}})"
                f'}}).then(()=>location.reload()); return false">'
                f'<input name="v" type="text" placeholder="New item"'
                f' style="border: 1px solid #ddd; padding: 2px 4px; width: 200px;"'
                f' oninput="{add_tooltip_js}" />'
                f' <button type="submit"'
                f' style="cursor: pointer; border: 1px solid #4a4; background: #efffef;'
                f' padding: 2px 8px; color: #2a2;"'
                f' title="{add_tooltip}">Add</button>'
                f'</form>'
            )

        # Remaining affordances (Clear, etc.)
        html += '<div style="margin-top: 8px;">'
        for aff in affs:
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'

        return html

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")
        items = list(self.items)

        if action == "add":
            value = body.get("value", "").strip()
            if not value:
                return self._error("Item value is required.", action=action)
            if value in items:
                return self._error(f"Duplicate: {value!r} is already in the set.", action=action)
            items.append(value)
            self._store.set(self._scope, self.key, items)

        elif action == "remove":
            value = body.get("value", "")
            if value not in items:
                return self._error(
                    f"Not in set: {value!r}. Current items: {', '.join(items)}",
                    action=action,
                )
            items.remove(value)
            self._store.set(self._scope, self.key, items)

        else:
            return self._error(f"Unknown action: {action}", action=action)

        return self.serialize()
