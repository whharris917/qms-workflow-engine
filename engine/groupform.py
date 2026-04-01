"""GroupForm — a named container for reusable eigenform compositions.

The simplest container: holds children, renders them, has identity.
No collapse, no tabs, no sequencing. Just grouping with a name.

Use GroupForm to define reusable named compositions:

    # Define once
    address = GroupForm(key="address", label="Address", eigenforms=[
        TextForm(key="street", label="Street"),
        TextForm(key="city", label="City"),
        ChoiceForm(key="country", label="Country", options=["US", "UK", "DE"]),
    ])

    # Use in multiple pages
    PageForm(key="shipping", eigenforms=[address, ...])
    PageForm(key="billing", eigenforms=[address, ...])

For parameterized compositions, subclass GroupForm:

    class Address(GroupForm):
        def __init__(self, key: str, countries: list[str] = None):
            super().__init__(key=key, label="Address", eigenforms=[
                TextForm(key="street", label="Street"),
                TextForm(key="city", label="City"),
                ChoiceForm(key="country", label="Country",
                           options=countries or ["US", "UK", "DE"]),
            ])

    PageForm(key="page", eigenforms=[
        Address("home", countries=["US", "CA", "MX"]),
        Address("work"),
    ])

bind() deepcopies the GroupForm, so the same definition can safely
appear in multiple pages.

Edit mode (when editable=True): exposes structural operations —
add, remove, and reorder eigenforms within the group. Structure is
persisted to the store so changes survive rebinds. Undo/discard
restore the full children scope (structure + data).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape

from engine.affordances import (
    Affordance,
    SetValueAffordance,
    SimpleButtonAffordance,
    render_inline_button,
)
from engine.eigenform import Eigenform
from engine.store import Store


@dataclass
class GroupForm(Eigenform):
    """A named group of eigenforms. The simplest container."""
    eigenforms: list[Eigenform] = field(default_factory=list)

    # Preserved during bind — unbound seed eigenforms for callable matching
    _seed: list[Eigenform] = field(default_factory=list, repr=False)

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["eigenforms"] = [ef.to_descriptor() for ef in self.eigenforms]
        return desc

    @property
    def children(self) -> list[Eigenform]:
        return self.eigenforms

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.eigenforms)

    def _bind_children(self, store: Store, url_prefix: str):
        self._seed = list(self.eigenforms)

        if self.editable:
            stored = store.get(self.key, "__structure")
            if stored is None:
                structure = [ef.to_descriptor() for ef in self._seed]
                store.set(self.key, "__structure", structure)
                source = self._seed
            else:
                source = self._reconstruct(stored)
        else:
            source = self.eigenforms

        self.eigenforms = [
            ef.bind(store=store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
            for ef in source
        ]

    def _reconstruct(self, stored_structure: list[dict]) -> list[Eigenform]:
        """Reconstruct eigenform list from stored descriptors + seed.

        The seed-match optimization in from_descriptor preserves callables
        but ignores descriptor-level field changes (like editable toggling).
        We apply editable from the descriptor after reconstruction so that
        parent-driven editability changes are honored.
        """
        from engine.registry import from_descriptor, get_registry
        seed_by_key = {ef.key: ef for ef in self._seed}
        reg = get_registry()
        result = []
        for desc in stored_structure:
            ef = from_descriptor(desc, reg, seed=seed_by_key.get(desc.get("key")))
            ef.editable = desc.get("editable", False)
            result.append(ef)
        return result

    def _rebuild(self):
        """Reconstruct the live eigenform tree from __structure."""
        stored = self._store.get(self.key, "__structure")
        if stored is None:
            return
        source = self._reconstruct(stored)
        self.eigenforms = [
            ef.bind(store=self._store, scope=self.key,
                    url_prefix=f"{self._url_prefix}/{self.key}")
            for ef in source
        ]

    def _get_structure(self) -> list[dict]:
        return list(self._store.get(self.key, "__structure") or [])

    def _save_structure(self, structure: list[dict]):
        self._store.set(self.key, "__structure", structure)

    # --- Edit mode ---

    def _snapshot_edit_state(self) -> dict:
        state = super()._snapshot_edit_state()
        state["__children_scope"] = self._store.snapshot_scope(self.key)
        return state

    def _restore_edit_state(self, state: dict):
        super()._restore_edit_state(state)
        self._store.restore_scope(self.key, state.get("__children_scope", {}))
        self._rebuild()

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()

        from engine.registry import get_registry
        reg = get_registry()
        available = reg.available()

        affs.append(SetValueAffordance(
            label="Add Eigenform",
            method="POST",
            url=self.url,
            body={
                "action": "add_eigenform",
                "type": "<type>",
                "key": "<unique_key>",
                "label": "<label>",
                "config": {},
                "after": "<sibling_key | null>",
            },
            instruction=(
                f"Add a new eigenform to this group. "
                f"Available types: {', '.join(available)}. "
                f"'after' places it after the named sibling (null = append to end). "
                f"'config' is type-specific (e.g. {{\"options\": [\"A\", \"B\"]}} for choice)."
            ),
        ))

        for ef in self.eigenforms:
            affs.append(SimpleButtonAffordance(
                label=f"Remove {ef.key}",
                method="POST",
                url=self.url,
                body={"action": "remove_eigenform", "key": ef.key},
                instruction=f"Remove the '{ef.key}' eigenform and its data.",
            ))

        if len(self.eigenforms) > 1:
            for ef in self.eigenforms:
                affs.append(SetValueAffordance(
                    label=f"Move {ef.key}",
                    method="POST",
                    url=self.url,
                    body={
                        "action": "move_eigenform",
                        "key": ef.key,
                        "position": "<index>",
                    },
                    instruction=(
                        f"Move '{ef.key}' to a new position (0-based index). "
                        f"Current order: {', '.join(e.key for e in self.eigenforms)}."
                    ),
                ))

        for ef in self.eigenforms:
            state = "on" if ef.editable else "off"
            affs.append(SimpleButtonAffordance(
                label=f"Toggle Editable {ef.key}",
                method="POST",
                url=self.url,
                body={"action": "toggle_editable", "key": ef.key},
                instruction=(
                    f"Toggle editability of '{ef.key}' "
                    f"(currently {'editable' if ef.editable else 'not editable'})."
                ),
            ))

        return affs

    # --- Structural mutation handlers ---

    def _clear_eigenform_data(self, ef: Eigenform):
        """Surgically clear stored data for one eigenform and its children."""
        if ef._store and ef._scope:
            ef._store.delete(ef._scope, ef.key)
        for child in ef.children:
            if child._scope and child._scope != ef._scope:
                self._store.clear_scope(child._scope)
            self._clear_eigenform_data(child)

    def _add_eigenform(self, body: dict) -> dict:
        from engine.registry import get_registry

        type_name = body.get("type")
        key = body.get("key")
        label = body.get("label", key)
        config = body.get("config", {})
        after = body.get("after")

        if not type_name or not key:
            return self._error("Both 'type' and 'key' are required.",
                               action="add_eigenform")

        reg = get_registry()
        if type_name not in reg:
            return self._error(
                f"Unknown type: {type_name}. "
                f"Available: {', '.join(reg.available())}",
                action="add_eigenform")

        existing_keys = {ef.key for ef in self.eigenforms}
        if key in existing_keys:
            return self._error(f"Key '{key}' already exists.",
                               action="add_eigenform")

        desc = {"type": type_name, "key": key, "label": label, "editable": True}
        if body.get("instruction"):
            desc["instruction"] = body["instruction"]
        if config:
            desc["config"] = config

        structure = self._get_structure()
        if after:
            idx = next((i for i, d in enumerate(structure)
                        if d["key"] == after), None)
            if idx is None:
                return self._error(f"Sibling '{after}' not found.",
                                   action="add_eigenform")
            structure.insert(idx + 1, desc)
        else:
            structure.append(desc)

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _remove_eigenform(self, body: dict) -> dict:
        key = body.get("key")
        if not key:
            return self._error("'key' is required.", action="remove_eigenform")

        ef = next((e for e in self.eigenforms if e.key == key), None)
        if ef is None:
            return self._error(f"Eigenform '{key}' not found.",
                               action="remove_eigenform")

        self._clear_eigenform_data(ef)

        structure = self._get_structure()
        structure = [d for d in structure if d["key"] != key]
        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _move_eigenform(self, body: dict) -> dict:
        key = body.get("key")
        position = body.get("position")

        if not key:
            return self._error("'key' is required.", action="move_eigenform")
        if position is None:
            return self._error("'position' is required.",
                               action="move_eigenform")

        try:
            position = int(position)
        except (TypeError, ValueError):
            return self._error(f"Invalid position: {position}",
                               action="move_eigenform")

        structure = self._get_structure()
        idx = next((i for i, d in enumerate(structure)
                    if d["key"] == key), None)
        if idx is None:
            return self._error(f"Eigenform '{key}' not found.",
                               action="move_eigenform")

        desc = structure.pop(idx)
        position = max(0, min(position, len(structure)))
        structure.insert(position, desc)

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _toggle_editable(self, body: dict) -> dict:
        key = body.get("key")
        if not key:
            return self._error("'key' is required.", action="toggle_editable")

        structure = self._get_structure()
        found = False
        for desc in structure:
            if desc["key"] == key:
                desc["editable"] = not desc.get("editable", False)
                found = True
                break

        if not found:
            return self._error(f"Eigenform '{key}' not found.",
                               action="toggle_editable")

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")

        if self.edit_mode:
            if action == "add_eigenform":
                self._push_undo()
                return self._add_eigenform(body)
            elif action == "remove_eigenform":
                self._push_undo()
                return self._remove_eigenform(body)
            elif action == "move_eigenform":
                self._push_undo()
                return self._move_eigenform(body)
            elif action == "toggle_editable":
                self._push_undo()
                return self._toggle_editable(body)

        return self.serialize()

    # --- Serialization ---

    def _serialize_state(self) -> dict:
        return self._base_state()

    def _serialize_full(self) -> dict:
        state = super()._serialize_full()
        state["eigenforms"] = [
            s for ef in self.eigenforms if (s := ef.serialize()) is not None
        ]
        return state

    def get_affordances(self):
        return []

    # --- Rendering ---

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html

        if data.get("edit_mode"):
            html = self._render_edit_header(data)
            html += self._render_edit_mode(data)
        else:
            html = f'<h3>{escape(data["label"])}</h3>'
            if data.get("instruction"):
                html += f'<p>{escape(data["instruction"])}</p>'
            html += "".join(ef.render() for ef in self.eigenforms)

        # Remaining affordances (Set Label, Set Instruction, Clear, etc.)
        html += '<div style="margin-top: 12px;">'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'
        return html

    def _render_edit_header(self, data: dict) -> str:
        """Render label and instruction as inline editable inputs in edit mode."""
        affs = data.get("affordances", [])
        url = self.url
        label = data.get("label", "")
        instruction = data.get("instruction") or ""

        # Mark Set Label / Set Instruction affordances as rendered
        for aff in affs:
            action = aff.get("body", {}).get("action", "")
            if action in ("set_label", "set_instruction"):
                Eigenform.mark_rendered(aff)

        INPUT_STYLE = (
            "font: inherit; border: 1px solid #ccc; border-radius: 3px;"
            " padding: 2px 6px; background: #fefefe;"
        )
        html = (
            f'<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">'
            f'<input type="text" value="{escape(label)}" id="{self.uid}-label"'
            f' style="{INPUT_STYLE} font-size: 1.17em; font-weight: bold; flex: 1;" />'
        )
        html += render_inline_button(
            url, {"action": "set_label", "label": "__JS__"},
            "&#10003;",
            "cursor: pointer; border: 1px solid #4a4; background: #efffef;"
            " width: 24px; height: 24px; font-size: 14px; padding: 0; color: #2a2;",
        ).replace(
            '"__JS__"',
            f"document.getElementById('{self.uid}-label').value",
        ).replace("JSON.stringify(", "JSON.stringify(Object.assign(")  # won't work — use a different approach
        # Simpler: use a custom onclick that reads the input
        html = (
            f'<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">'
            f'<input type="text" value="{escape(label)}" id="{self.uid}-label"'
            f' style="{INPUT_STYLE} font-size: 1.17em; font-weight: bold; flex: 1;" />'
            f'<button onclick="fetch(\'{url}\',{{method:\'POST\','
            f'headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{action:\'set_label\','
            f'label:document.getElementById(\'{self.uid}-label\').value}})'
            f'}}).then(()=>location.reload())"'
            f' style="cursor: pointer; border: 1px solid #4a4; background: #efffef;'
            f' width: 24px; height: 24px; font-size: 14px; padding: 0; color: #2a2;"'
            f' title="Confirm label">&#10003;</button>'
            f'</div>'
        )
        html += (
            f'<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 8px;">'
            f'<input type="text" value="{escape(instruction)}" id="{self.uid}-instr"'
            f' placeholder="Instruction text (optional)"'
            f' style="{INPUT_STYLE} flex: 1; color: #555;" />'
            f'<button onclick="fetch(\'{url}\',{{method:\'POST\','
            f'headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{action:\'set_instruction\','
            f'instruction:document.getElementById(\'{self.uid}-instr\').value}})'
            f'}}).then(()=>location.reload())"'
            f' style="cursor: pointer; border: 1px solid #4a4; background: #efffef;'
            f' width: 24px; height: 24px; font-size: 14px; padding: 0; color: #2a2;"'
            f' title="Confirm instruction">&#10003;</button>'
            f'</div>'
        )
        return html

    def _render_edit_mode(self, data: dict) -> str:
        """Render the group with an add toolbar and per-eigenform controls."""
        from engine.registry import get_registry
        affs = data.get("affordances", [])
        url = self.url

        # Mark structural affordances as rendered (custom HTML handles them)
        for aff in affs:
            body = aff.get("body", {})
            action = body.get("action", "")
            if action in ("add_eigenform", "remove_eigenform",
                          "move_eigenform", "toggle_editable"):
                Eigenform.mark_rendered(aff)

        # --- Add toolbar ---
        reg = get_registry()
        available = sorted(reg.available())
        type_options = "".join(
            f'<option value="{escape(t)}">{escape(t)}</option>'
            for t in available
        )
        html = (
            f'<div style="background: #f5f5f5; border: 1px solid #ddd; padding: 10px;'
            f' margin-bottom: 12px; border-radius: 4px;">'
            f'<form style="display: flex; gap: 8px; align-items: end; flex-wrap: wrap;"'
            f' onsubmit="'
            f"var b={{action:'add_eigenform',type:this.elements.t.value,"
            f"key:this.elements.k.value,label:this.elements.l.value,config:{{}}}};"
            f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
            f'<div><label style="font-size: 11px; color: #666; display: block;">Type</label>'
            f'<select name="t" style="padding: 4px;">'
            f'<option value="">-- select type --</option>{type_options}</select></div>'
            f'<div><label style="font-size: 11px; color: #666; display: block;">Key</label>'
            f'<input name="k" type="text" placeholder="unique-key"'
            f' style="padding: 4px; width: 140px;" /></div>'
            f'<div><label style="font-size: 11px; color: #666; display: block;">Label</label>'
            f'<input name="l" type="text" placeholder="Display Label"'
            f' style="padding: 4px; width: 160px;" /></div>'
            f'<button type="submit" style="padding: 4px 14px; cursor: pointer;'
            f' background: #4a7; color: white; border: 1px solid #396;'
            f' border-radius: 3px;">+ Add</button>'
            f'</form></div>'
        )

        # --- Eigenforms with inline controls ---
        n = len(self.eigenforms)
        for i, ef in enumerate(self.eigenforms):
            key = ef.key
            ctrl = (
                f'<div style="display: flex; align-items: center; gap: 4px;'
                f' padding: 4px 8px; background: #fafafa; border: 1px solid #e0e0e0;'
                f' border-bottom: none; border-radius: 4px 4px 0 0;'
                f' font-size: 11px; color: #666;">'
                f'<span style="font-family: monospace; background: #eee;'
                f' padding: 1px 5px; border-radius: 2px;">{escape(key)}</span>'
                f'<span style="flex: 1;"></span>'
            )
            if i > 0:
                ctrl += render_inline_button(
                    url, {"action": "move_eigenform", "key": key, "position": i - 1},
                    "&#9650;",
                    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
                    " width: 22px; height: 22px; font-size: 9px; padding: 0;",
                )
            else:
                ctrl += (
                    '<span style="display: inline-block; width: 22px; height: 22px;'
                    ' border: 1px solid transparent;"></span>'
                )
            if i < n - 1:
                ctrl += render_inline_button(
                    url, {"action": "move_eigenform", "key": key, "position": i + 1},
                    "&#9660;",
                    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
                    " width: 22px; height: 22px; font-size: 9px; padding: 0;",
                )
            else:
                ctrl += (
                    '<span style="display: inline-block; width: 22px; height: 22px;'
                    ' border: 1px solid transparent;"></span>'
                )
            # Editable toggle — pencil icon, highlighted when on
            if ef.editable:
                edit_style = (
                    "cursor: pointer; border: 1px solid #86c; background: #f3eaff;"
                    " width: 22px; height: 22px; font-size: 11px; padding: 0;"
                    " color: #639;"
                )
            else:
                edit_style = (
                    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
                    " width: 22px; height: 22px; font-size: 11px; padding: 0;"
                    " color: #aaa;"
                )
            ctrl += render_inline_button(
                url, {"action": "toggle_editable", "key": key},
                "&#9998;", edit_style,
            )
            ctrl += render_inline_button(
                url, {"action": "remove_eigenform", "key": key},
                "&#10005;",
                "cursor: pointer; border: 1px solid #dcc; background: #fef8f8;"
                " width: 22px; height: 22px; font-size: 10px; padding: 0; color: #c00;"
                " margin-left: 4px;",
            )
            ctrl += '</div>'

            html += (
                f'<div style="margin-bottom: 8px;">'
                f'{ctrl}'
                f'<div style="border: 1px solid #e0e0e0; border-radius: 0 0 4px 4px;'
                f' padding: 8px;">'
                f'{ef.render()}'
                f'</div></div>'
            )

        if not self.eigenforms:
            html += (
                '<div style="padding: 24px; text-align: center; color: #999;'
                ' border: 2px dashed #ddd; border-radius: 4px;'
                ' margin-bottom: 8px;">'
                'No eigenforms yet. Use the toolbar above to add one.</div>'
            )

        return html
