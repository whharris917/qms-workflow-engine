"""CheckboxForm — multi-select with explicit confirmation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape

from engine.affordances import Affordance, CheckboxAffordance, SimpleButtonAffordance, STYLE_CONFIRM
from engine.eigenform import Eigenform


@dataclass
class CheckboxForm(Eigenform):
    """Multi-select: a set of items, each independently selectable.

    Requires explicit confirmation via a "Done" action to be considered
    complete. This prevents premature auto-advance in ChainForm when
    the user has only checked one item but intends to check more.

    Done with no items checked means "none of these apply."
    Toggling any item after confirmation clears the confirmed state.
    """
    items: list[str] = field(default_factory=list)

    def __post_init__(self):
        from engine.listform import ListForm
        self._items_form = ListForm(
            key="__items",
            label="Items",
            allow_constraints=False,
        )

    @property
    def children(self) -> list[Eigenform]:
        if self.edit_mode:
            return [self._items_form]
        return []

    def _bind_children(self, store, url_prefix):
        self._items_form = self._items_form.bind(
            store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
        # Seed initial items if no ListForm data exists yet
        if not self._items_form.value:
            for item in self.items:
                self._items_form.handle({"action": "add", "value": item})
        # Wrap child handle so CheckboxForm pushes undo before ListForm changes
        original_handle = self._items_form.handle
        parent = self
        def _handle_with_undo(body):
            if parent.edit_mode:
                parent._push_undo()
            return original_handle(body)
        self._items_form.handle = _handle_with_undo

    def _snapshot_edit_state(self) -> dict:
        state = super()._snapshot_edit_state()
        state["__items"] = self._store.get(self.key, "__items")
        return state

    def _restore_edit_state(self, state: dict):
        super()._restore_edit_state(state)
        self._store.set(self.key, "__items", state.get("__items"))

    @property
    def _effective_items(self) -> list[str]:
        """Read current items from the child ListForm."""
        return [item["value"] for item in self._items_form.items]

    @property
    def checked(self) -> dict[str, bool]:
        """Current state: {item: bool} for each item."""
        stored = self.value or {}
        return {item: stored.get(item, False) for item in self._effective_items}

    @property
    def confirmed(self) -> bool:
        """Whether the selection has been explicitly confirmed."""
        stored = self.value or {}
        return bool(stored.get("__confirmed"))

    @property
    def is_complete(self) -> bool:
        return self.confirmed

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "items": self.checked,
            "confirmed": self.confirmed,
        }

    def get_affordances(self) -> list[Affordance]:
        items = self._effective_items
        affs = [
            CheckboxAffordance(
                label=f"Set {self.effective_label}",
                method="POST",
                url=self.url,
                body={item: "<true | false>" for item in items},
                instruction="Set one or more items. Omitted items are unchanged.",
                items=self.checked,
            ),
        ]
        if not self.confirmed:
            affs.append(SimpleButtonAffordance(
                label="Done",
                method="POST",
                url=self.url,
                body={"action": "done"},
                instruction="Confirm the current selection (or none selected = none apply).",
            ))
        return affs

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html

        if data.get("edit_mode"):
            return self._render_edit_mode(data)

        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        return html

    def _render_edit_mode(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
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

        # Items — render the child ListForm
        html += self._items_form.render()

        # Confirmed state
        if data.get("confirmed"):
            html += '<div style="color: #2a2; font-size: 0.9em; margin-top: 4px;">&#10003; Confirmed</div>'

        # Mark edit affordances as rendered
        edit_actions = {"set_label", "set_instruction"}
        for aff in data.get("affordances", []):
            if aff.get("_rendered"):
                continue
            if aff.get("body", {}).get("action") in edit_actions:
                aff["_rendered"] = True
            else:
                html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        action = body.get("action")
        if action == "done":
            stored = dict(self.value or {})
            stored["__confirmed"] = True
            self._store.set(self._scope, self.key, stored)
        else:
            current = self.checked
            changed = False
            for item_key, value in body.items():
                if item_key in current:
                    current[item_key] = value
                    changed = True
            if changed:
                current["__confirmed"] = False
            self._store.set(self._scope, self.key, current)
        return self.serialize()
