"""AccordionForm — collapsible sections, all visible simultaneously.

Unlike TabForm (one-at-a-time), AccordionForm shows all sections with
expand/collapse toggles. Unlike PageForm (always shows everything),
AccordionForm adds collapsibility.

Collapsed sections are omitted from both JSON and HTML — faithful
projection requires the agent and human to see the same information.
The toggle affordances are always present so both can expand any section.

Edit mode (when editable=True): exposes structural operations —
add, remove, reorder sections, and toggle editability on section
eigenforms. Structure is persisted to the store so changes survive
rebinds.
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


class ToggleSectionAffordance(Affordance):
    """An affordance to expand/collapse an accordion section."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None, expanded: bool = True):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.expanded = expanded

    def _render_hints(self) -> dict:
        return {"type": "accordion_toggle", "expanded": self.expanded}


@dataclass
class AccordionForm(Eigenform):
    """A container with collapsible sections."""
    sections: dict[str, Eigenform] = field(default_factory=dict)

    # Preserved during bind — unbound seed sections for callable matching
    _seed: dict[str, Eigenform] = field(default_factory=dict, repr=False)

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["sections"] = {k: v.to_descriptor() for k, v in self.sections.items()}
        return desc

    @property
    def children(self) -> list[Eigenform]:
        return list(self.sections.values())

    @property
    def _expanded_state(self) -> dict[str, bool]:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored
        return {}

    def _is_expanded(self, section_key: str) -> bool:
        return self._expanded_state.get(section_key, True)

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.sections.values())

    # --- Structural persistence ---

    def _bind_children(self, store: Store, url_prefix: str):
        self._seed = dict(self.sections)

        if self.editable:
            stored = store.get(self.key, "__structure")
            if stored is None:
                structure = [
                    {"section_key": k, "eigenform": v.to_descriptor()}
                    for k, v in self._seed.items()
                ]
                store.set(self.key, "__structure", structure)
                source = self._seed
            else:
                source = self._reconstruct(stored)
        else:
            source = self.sections

        self.sections = {
            sec_key: ef.bind(store=store, scope=self.key,
                             url_prefix=f"{url_prefix}/{self.key}")
            for sec_key, ef in source.items()
        }

    def _reconstruct(self, stored_structure: list[dict]) -> dict[str, Eigenform]:
        from engine.registry import from_descriptor, get_registry
        seed_by_key = {ef.key: ef for ef in self._seed.values()}
        reg = get_registry()
        result = {}
        for entry in stored_structure:
            sec_key = entry["section_key"]
            desc = entry["eigenform"]
            ef = from_descriptor(desc, reg, seed=seed_by_key.get(desc.get("key")))
            ef.editable = desc.get("editable", False)
            result[sec_key] = ef
        return result

    def _rebuild(self):
        stored = self._store.get(self.key, "__structure")
        if stored is None:
            return
        source = self._reconstruct(stored)
        self.sections = {
            sec_key: ef.bind(store=self._store, scope=self.key,
                             url_prefix=f"{self._url_prefix}/{self.key}")
            for sec_key, ef in source.items()
        }

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

    def _toggle_affordances(self) -> list[Affordance]:
        """Section toggle affordances — shared by both modes."""
        affordances = []
        for sec_key, ef in self.sections.items():
            expanded = self._is_expanded(sec_key)
            affordances.append(ToggleSectionAffordance(
                label=ef.effective_label,
                method="POST",
                url=self.url,
                body={"action": "toggle", "section": sec_key},
                instruction=f"{'Collapse' if expanded else 'Expand'} the {ef.effective_label} section.",
                expanded=expanded,
            ))
        return affordances

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        affs.extend(self._toggle_affordances())

        from engine.registry import get_registry
        reg = get_registry()
        available = reg.available()

        affs.append(SetValueAffordance(
            label="Add Section",
            method="POST",
            url=self.url,
            body={
                "action": "add_section",
                "section_key": "<section_key>",
                "type": "<type>",
                "key": "<eigenform_key>",
                "label": "<label>",
                "config": {},
                "after": "<sibling_section_key | null>",
            },
            instruction=(
                f"Add a new section. 'section_key' is the section identifier. "
                f"Available types: {', '.join(available)}. "
                f"'after' places it after the named section (null = append to end)."
            ),
        ))

        sec_keys = list(self.sections.keys())
        for sec_key, ef in self.sections.items():
            affs.append(SimpleButtonAffordance(
                label=f"Remove Section {sec_key}",
                method="POST",
                url=self.url,
                body={"action": "remove_section", "section_key": sec_key},
                instruction=f"Remove the '{sec_key}' section and its data.",
            ))
            state = "editable" if ef.editable else "not editable"
            affs.append(SimpleButtonAffordance(
                label=f"Toggle Editable {sec_key}",
                method="POST",
                url=self.url,
                body={"action": "toggle_editable", "section_key": sec_key},
                instruction=f"Toggle editability of '{sec_key}' (currently {state}).",
            ))

        if len(self.sections) > 1:
            for sec_key in sec_keys:
                affs.append(SetValueAffordance(
                    label=f"Move Section {sec_key}",
                    method="POST",
                    url=self.url,
                    body={
                        "action": "move_section",
                        "section_key": sec_key,
                        "position": "<index>",
                    },
                    instruction=(
                        f"Move '{sec_key}' to a new position (0-based index). "
                        f"Current order: {', '.join(sec_keys)}."
                    ),
                ))

        return affs

    # --- Structural mutation handlers ---

    def _clear_eigenform_data(self, ef: Eigenform):
        if ef._store and ef._scope:
            ef._store.delete(ef._scope, ef.key)
        for child in ef.children:
            if child._scope and child._scope != ef._scope:
                self._store.clear_scope(child._scope)
            self._clear_eigenform_data(child)

    def _add_section(self, body: dict) -> dict:
        from engine.registry import get_registry

        section_key = body.get("section_key")
        type_name = body.get("type")
        key = body.get("key")
        label = body.get("label", key)
        config = body.get("config", {})
        after = body.get("after")

        if not section_key or not type_name or not key:
            return self._error(
                "'section_key', 'type', and 'key' are required.",
                action="add_section")

        reg = get_registry()
        if type_name not in reg:
            return self._error(
                f"Unknown type: {type_name}. "
                f"Available: {', '.join(reg.available())}",
                action="add_section")

        if section_key in self.sections:
            return self._error(f"Section key '{section_key}' already exists.",
                               action="add_section")

        existing_ef_keys = {ef.key for ef in self.sections.values()}
        if key in existing_ef_keys:
            return self._error(f"Eigenform key '{key}' already exists.",
                               action="add_section")

        desc = {"type": type_name, "key": key, "label": label, "editable": True}
        if body.get("instruction"):
            desc["instruction"] = body["instruction"]
        if config:
            desc["config"] = config

        structure = self._get_structure()
        entry = {"section_key": section_key, "eigenform": desc}
        if after:
            idx = next((i for i, e in enumerate(structure)
                        if e["section_key"] == after), None)
            if idx is None:
                return self._error(f"Section '{after}' not found.",
                                   action="add_section")
            structure.insert(idx + 1, entry)
        else:
            structure.append(entry)

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _remove_section(self, body: dict) -> dict:
        section_key = body.get("section_key")
        if not section_key:
            return self._error("'section_key' is required.",
                               action="remove_section")

        ef = self.sections.get(section_key)
        if ef is None:
            return self._error(f"Section '{section_key}' not found.",
                               action="remove_section")

        self._clear_eigenform_data(ef)

        structure = self._get_structure()
        structure = [e for e in structure if e["section_key"] != section_key]
        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _move_section(self, body: dict) -> dict:
        section_key = body.get("section_key")
        position = body.get("position")

        if not section_key:
            return self._error("'section_key' is required.",
                               action="move_section")
        if position is None:
            return self._error("'position' is required.",
                               action="move_section")

        try:
            position = int(position)
        except (TypeError, ValueError):
            return self._error(f"Invalid position: {position}",
                               action="move_section")

        structure = self._get_structure()
        idx = next((i for i, e in enumerate(structure)
                    if e["section_key"] == section_key), None)
        if idx is None:
            return self._error(f"Section '{section_key}' not found.",
                               action="move_section")

        entry = structure.pop(idx)
        position = max(0, min(position, len(structure)))
        structure.insert(position, entry)

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _toggle_editable(self, body: dict) -> dict:
        section_key = body.get("section_key")
        if not section_key:
            return self._error("'section_key' is required.",
                               action="toggle_editable")

        structure = self._get_structure()
        found = False
        for entry in structure:
            if entry["section_key"] == section_key:
                desc = entry["eigenform"]
                desc["editable"] = not desc.get("editable", False)
                found = True
                break

        if not found:
            return self._error(f"Section '{section_key}' not found.",
                               action="toggle_editable")

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")

        # Toggle expand/collapse works in both modes
        if action == "toggle":
            sec_key = body.get("section")
            if sec_key in self.sections:
                state = dict(self._expanded_state)
                state[sec_key] = not self._is_expanded(sec_key)
                self._store.set(self._scope, self.key, state)
            return self.serialize()

        if self.edit_mode:
            if action == "add_section":
                self._push_undo()
                return self._add_section(body)
            elif action == "remove_section":
                self._push_undo()
                return self._remove_section(body)
            elif action == "move_section":
                self._push_undo()
                return self._move_section(body)
            elif action == "toggle_editable":
                self._push_undo()
                return self._toggle_editable(body)

        return self.serialize()

    # --- Serialization ---

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "section_keys": list(self.sections.keys()),
        }

    def _serialize_full(self) -> dict:
        state = super()._serialize_full()
        state["sections"] = {}
        for sec_key, ef in self.sections.items():
            expanded = self._is_expanded(sec_key)
            entry = {"expanded": expanded}
            if expanded:
                entry["eigenform"] = ef.serialize()
            state["sections"][sec_key] = entry
        return state

    def get_affordances(self) -> list[Affordance]:
        return self._toggle_affordances()

    # --- Rendering ---

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html

        if data.get("edit_mode"):
            html = self._render_edit_header(data)
            html += self._render_edit_sections(data)
        else:
            html = f'<h3>{escape(data["label"])}</h3>'
            if data.get("instruction"):
                html += f'<p>{escape(data["instruction"])}</p>'
            html += self._render_sections(data)

        # Remaining affordances
        html += '<div style="margin-top: 12px;">'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'
        return html

    def _render_sections(self, data: dict) -> str:
        """Render sections with toggle headers (execution mode)."""
        from engine.affordances import render_affordance_html
        sections = data.get("sections", {})
        affs = data.get("affordances", [])
        html = ""

        for sec_key in data.get("section_keys", []):
            sec_data = sections.get(sec_key, {})
            expanded = sec_data.get("expanded", True)

            for aff in affs:
                if aff.get("body", {}).get("section") == sec_key:
                    html += render_affordance_html(aff)
                    break

            if expanded:
                ef = self.sections.get(sec_key)
                if ef:
                    html += (
                        '<div style="padding-left: 12px; border-left: 2px solid #ddd;'
                        ' margin-bottom: 8px;">'
                    )
                    html += ef.render()
                    html += '</div>'

        return html

    def _render_edit_header(self, data: dict) -> str:
        affs = data.get("affordances", [])
        url = self.url
        label = data.get("label", "")
        instruction = data.get("instruction") or ""

        for aff in affs:
            action = aff.get("body", {}).get("action", "")
            if action in ("set_label", "set_instruction"):
                Eigenform.mark_rendered(aff)

        INPUT_STYLE = (
            "font: inherit; border: 1px solid #ccc; border-radius: 3px;"
            " padding: 2px 6px; background: #fefefe;"
        )
        CONFIRM = (
            "cursor: pointer; border: 1px solid #4a4; background: #efffef;"
            " width: 24px; height: 24px; font-size: 14px; padding: 0; color: #2a2;"
        )
        html = (
            f'<div style="display: flex; align-items: center; gap: 6px;'
            f' margin-bottom: 4px;">'
            f'<input type="text" value="{escape(label)}" id="{self.uid}-label"'
            f' style="{INPUT_STYLE} font-size: 1.17em; font-weight: bold; flex: 1;" />'
            f'<button onclick="fetch(\'{url}\',{{method:\'POST\','
            f'headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{action:\'set_label\','
            f'label:document.getElementById(\'{self.uid}-label\').value}})'
            f'}}).then(()=>location.reload())"'
            f' style="{CONFIRM}" title="Confirm label">&#10003;</button>'
            f'</div>'
        )
        html += (
            f'<div style="display: flex; align-items: center; gap: 6px;'
            f' margin-bottom: 8px;">'
            f'<input type="text" value="{escape(instruction)}" id="{self.uid}-instr"'
            f' placeholder="Instruction text (optional)"'
            f' style="{INPUT_STYLE} flex: 1; color: #555;" />'
            f'<button onclick="fetch(\'{url}\',{{method:\'POST\','
            f'headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{action:\'set_instruction\','
            f'instruction:document.getElementById(\'{self.uid}-instr\').value}})'
            f'}}).then(()=>location.reload())"'
            f' style="{CONFIRM}" title="Confirm instruction">&#10003;</button>'
            f'</div>'
        )
        return html

    def _render_edit_sections(self, data: dict) -> str:
        """Render sections with add toolbar and per-section controls."""
        from engine.registry import get_registry
        from engine.affordances import render_affordance_html
        affs = data.get("affordances", [])
        sections_data = data.get("sections", {})
        url = self.url

        # Mark structural affordances as rendered
        for aff in affs:
            body = aff.get("body", {})
            action = body.get("action", "")
            if action in ("add_section", "remove_section", "move_section",
                          "toggle_editable"):
                Eigenform.mark_rendered(aff)
            # Toggle affordances rendered inline below
            elif action == "toggle":
                Eigenform.mark_rendered(aff)

        # Add toolbar
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
            f"var b={{action:'add_section',section_key:this.elements.sk.value,"
            f"type:this.elements.t.value,"
            f"key:this.elements.k.value,label:this.elements.l.value,config:{{}}}};"
            f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
            f'<div><label style="font-size: 11px; color: #666; display: block;">Section Key</label>'
            f'<input name="sk" type="text" placeholder="section-key"'
            f' style="padding: 4px; width: 100px;" /></div>'
            f'<div><label style="font-size: 11px; color: #666; display: block;">Type</label>'
            f'<select name="t" style="padding: 4px;">'
            f'<option value="">-- type --</option>{type_options}</select></div>'
            f'<div><label style="font-size: 11px; color: #666; display: block;">Key</label>'
            f'<input name="k" type="text" placeholder="eigenform-key"'
            f' style="padding: 4px; width: 120px;" /></div>'
            f'<div><label style="font-size: 11px; color: #666; display: block;">Label</label>'
            f'<input name="l" type="text" placeholder="Section Label"'
            f' style="padding: 4px; width: 140px;" /></div>'
            f'<button type="submit" style="padding: 4px 14px; cursor: pointer;'
            f' background: #4a7; color: white; border: 1px solid #396;'
            f' border-radius: 3px;">+ Add</button>'
            f'</form></div>'
        )

        # Sections with controls
        sec_keys = list(self.sections.keys())
        n = len(sec_keys)
        for i, sec_key in enumerate(sec_keys):
            ef = self.sections[sec_key]
            expanded = self._is_expanded(sec_key)
            sec_data = sections_data.get(sec_key, {})

            # Section header with controls
            arrow = "&#9660;" if expanded else "&#9654;"
            html += (
                f'<div style="display: flex; align-items: center; gap: 4px;'
                f' padding: 4px 8px; background: #fafafa; border: 1px solid #e0e0e0;'
                f' border-radius: 4px; margin-bottom: {"0" if expanded else "4"}px;'
                f' {"border-bottom-left-radius: 0; border-bottom-right-radius: 0;" if expanded else ""}'
                f' font-size: 12px;">'
            )

            # Toggle expand/collapse
            html += render_inline_button(
                url, {"action": "toggle", "section": sec_key},
                arrow,
                "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
                " width: 22px; height: 22px; font-size: 10px; padding: 0;",
            )

            # Section label
            html += (
                f'<span style="font-weight: bold; flex: 1;">'
                f'{escape(ef.effective_label)}'
                f'<span style="font-family: monospace; font-weight: normal;'
                f' font-size: 10px; color: #999; margin-left: 6px;">{escape(sec_key)}</span>'
                f'</span>'
            )

            # Move up/down
            if i > 0:
                html += render_inline_button(
                    url, {"action": "move_section", "section_key": sec_key,
                          "position": i - 1},
                    "&#9650;",
                    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
                    " width: 18px; height: 18px; font-size: 8px; padding: 0;",
                )
            if i < n - 1:
                html += render_inline_button(
                    url, {"action": "move_section", "section_key": sec_key,
                          "position": i + 1},
                    "&#9660;",
                    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
                    " width: 18px; height: 18px; font-size: 8px; padding: 0;",
                )

            # Toggle editable
            if ef.editable:
                edit_style = (
                    "cursor: pointer; border: 1px solid #86c; background: #f3eaff;"
                    " width: 18px; height: 18px; font-size: 10px; padding: 0; color: #639;"
                )
            else:
                edit_style = (
                    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
                    " width: 18px; height: 18px; font-size: 10px; padding: 0; color: #aaa;"
                )
            html += render_inline_button(
                url, {"action": "toggle_editable", "section_key": sec_key},
                "&#9998;", edit_style,
            )

            # Remove
            html += render_inline_button(
                url, {"action": "remove_section", "section_key": sec_key},
                "&#10005;",
                "cursor: pointer; border: 1px solid #dcc; background: #fef8f8;"
                " width: 18px; height: 18px; font-size: 9px; padding: 0; color: #c00;",
            )

            html += '</div>'

            # Section content if expanded
            if expanded:
                html += (
                    '<div style="padding-left: 12px; border-left: 2px solid #ddd;'
                    ' border: 1px solid #e0e0e0; border-top: none;'
                    ' border-radius: 0 0 4px 4px; padding: 8px; margin-bottom: 4px;">'
                )
                html += ef.render()
                html += '</div>'

        if not self.sections:
            html += (
                '<div style="padding: 24px; text-align: center; color: #999;'
                ' border: 2px dashed #ddd; border-radius: 4px; margin-bottom: 8px;">'
                'No sections yet. Use the toolbar above to add one.</div>'
            )

        return html

    def handle_action(self, key: str, body: dict) -> bool:
        """Route action: toggle goes to self, otherwise search all sections."""
        if key == self.key:
            self.handle(body)
            return True
        for ef in self.sections.values():
            if ef.key == key:
                ef.handle(body)
                return True
            if hasattr(ef, 'handle_action') and ef.handle_action(key, body):
                return True
        return False
