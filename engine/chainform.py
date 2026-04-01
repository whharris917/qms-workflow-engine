"""ChainForm — a sequence of eigenforms shown one at a time.

Only the first incomplete eigenform is visible. Completed eigenforms
appear as "jump back" affordances, allowing revisitation. Both the
agent and human see the same thing — faithful projection.

Edit mode (when editable=True): exposes structural operations —
add, remove, reorder steps, and toggle editability on step eigenforms.
Structure is persisted to the store so changes survive rebinds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

from engine.affordances import (
    Affordance,
    SetValueAffordance,
    SimpleButtonAffordance,
    SwitchTabAffordance,
    render_inline_button,
)
from engine.eigenform import Eigenform
from engine.store import Store


@dataclass
class ChainForm(Eigenform):
    """A sequence of eigenforms, auto-advancing through them one at a time."""
    steps: list[Eigenform] = field(default_factory=list)

    # Preserved during bind — unbound seed steps for callable matching
    _seed: list[Eigenform] = field(default_factory=list, repr=False)

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["steps"] = [ef.to_descriptor() for ef in self.steps]
        return desc

    @property
    def children(self) -> list[Eigenform]:
        return self.steps

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.steps)

    @property
    def _focused_key(self) -> str | None:
        """The key of the currently focused step, from the store."""
        stored = self.value
        if stored and stored in {ef.key for ef in self.steps}:
            return stored
        return None

    @property
    def active_step(self) -> Eigenform | None:
        """The currently visible step: explicitly focused, or first incomplete."""
        focused = self._focused_key
        if focused:
            for ef in self.steps:
                if ef.key == focused:
                    return ef
        for ef in self.steps:
            if not ef.is_complete:
                return ef
        return self.steps[-1] if self.steps else None

    @property
    def active_key(self) -> str | None:
        active = self.active_step
        return active.key if active else None

    # --- Structural persistence ---

    def _bind_children(self, store: Store, url_prefix: str):
        self._seed = list(self.steps)

        if self.editable:
            stored = store.get(self.key, "__structure")
            if stored is None:
                structure = [ef.to_descriptor() for ef in self._seed]
                store.set(self.key, "__structure", structure)
                source = self._seed
            else:
                source = self._reconstruct(stored)
        else:
            source = self.steps

        self.steps = [
            ef.bind(store=store, scope=self.key,
                    url_prefix=f"{url_prefix}/{self.key}")
            for ef in source
        ]

    def _reconstruct(self, stored_structure: list[dict]) -> list[Eigenform]:
        """Reconstruct steps list from stored descriptors + seed."""
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
        stored = self._store.get(self.key, "__structure")
        if stored is None:
            return
        source = self._reconstruct(stored)
        self.steps = [
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

    def _nav_affordances(self) -> list[Affordance]:
        """Navigation affordances (focus/continue) — shared by both modes."""
        affordances = []
        active = self.active_step
        if active and active.is_complete and self._focused_key is not None:
            affordances.append(SimpleButtonAffordance(
                label="Continue",
                method="POST",
                url=self.url,
                body={"action": "continue"},
                instruction="Resume from the next incomplete step.",
            ))
        for ef in self.steps:
            if ef.is_complete and ef.key != self.active_key:
                affordances.append(SwitchTabAffordance(
                    label=f"Back to {ef.effective_label}",
                    method="POST",
                    url=self.url,
                    body={"focus": ef.key},
                    instruction=f"Jump back to the completed {ef.effective_label} step.",
                ))
        return affordances

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        affs.extend(self._nav_affordances())

        from engine.registry import get_registry
        reg = get_registry()
        available = reg.available()

        affs.append(SetValueAffordance(
            label="Add Step",
            method="POST",
            url=self.url,
            body={
                "action": "add_step",
                "type": "<type>",
                "key": "<unique_key>",
                "label": "<label>",
                "config": {},
                "after": "<sibling_key | null>",
            },
            instruction=(
                f"Add a new step to this chain. "
                f"Available types: {', '.join(available)}. "
                f"'after' places it after the named sibling (null = append to end)."
            ),
        ))

        for ef in self.steps:
            affs.append(SimpleButtonAffordance(
                label=f"Remove {ef.key}",
                method="POST",
                url=self.url,
                body={"action": "remove_step", "key": ef.key},
                instruction=f"Remove the '{ef.key}' step and its data.",
            ))
            state = "editable" if ef.editable else "not editable"
            affs.append(SimpleButtonAffordance(
                label=f"Toggle Editable {ef.key}",
                method="POST",
                url=self.url,
                body={"action": "toggle_editable", "key": ef.key},
                instruction=f"Toggle editability of '{ef.key}' (currently {state}).",
            ))

        if len(self.steps) > 1:
            for ef in self.steps:
                affs.append(SetValueAffordance(
                    label=f"Move {ef.key}",
                    method="POST",
                    url=self.url,
                    body={
                        "action": "move_step",
                        "key": ef.key,
                        "position": "<index>",
                    },
                    instruction=(
                        f"Move '{ef.key}' to a new position (0-based index). "
                        f"Current order: {', '.join(e.key for e in self.steps)}."
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

    def _add_step(self, body: dict) -> dict:
        from engine.registry import get_registry

        type_name = body.get("type")
        key = body.get("key")
        label = body.get("label", key)
        config = body.get("config", {})
        after = body.get("after")

        if not type_name or not key:
            return self._error("Both 'type' and 'key' are required.",
                               action="add_step")

        reg = get_registry()
        if type_name not in reg:
            return self._error(
                f"Unknown type: {type_name}. "
                f"Available: {', '.join(reg.available())}",
                action="add_step")

        if key in {ef.key for ef in self.steps}:
            return self._error(f"Key '{key}' already exists.",
                               action="add_step")

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
                return self._error(f"Step '{after}' not found.",
                                   action="add_step")
            structure.insert(idx + 1, desc)
        else:
            structure.append(desc)

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _remove_step(self, body: dict) -> dict:
        key = body.get("key")
        if not key:
            return self._error("'key' is required.", action="remove_step")

        ef = next((e for e in self.steps if e.key == key), None)
        if ef is None:
            return self._error(f"Step '{key}' not found.",
                               action="remove_step")

        self._clear_eigenform_data(ef)

        structure = self._get_structure()
        structure = [d for d in structure if d["key"] != key]
        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _move_step(self, body: dict) -> dict:
        key = body.get("key")
        position = body.get("position")

        if not key:
            return self._error("'key' is required.", action="move_step")
        if position is None:
            return self._error("'position' is required.", action="move_step")

        try:
            position = int(position)
        except (TypeError, ValueError):
            return self._error(f"Invalid position: {position}",
                               action="move_step")

        structure = self._get_structure()
        idx = next((i for i, d in enumerate(structure)
                    if d["key"] == key), None)
        if idx is None:
            return self._error(f"Step '{key}' not found.",
                               action="move_step")

        desc = structure.pop(idx)
        position = max(0, min(position, len(structure)))
        structure.insert(position, desc)

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _toggle_editable(self, body: dict) -> dict:
        key = body.get("key")
        if not key:
            return self._error("'key' is required.",
                               action="toggle_editable")

        structure = self._get_structure()
        found = False
        for desc in structure:
            if desc["key"] == key:
                desc["editable"] = not desc.get("editable", False)
                found = True
                break

        if not found:
            return self._error(f"Step '{key}' not found.",
                               action="toggle_editable")

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _handle(self, body: dict) -> dict:
        """Handle focus change, continue, or structural actions."""
        action = body.get("action", "")

        # Navigation works in both modes
        if action == "continue":
            self._store.set(self._scope, self.key, None)
            return self.serialize()
        focus = body.get("focus")
        if focus and focus in {ef.key for ef in self.steps}:
            self._store.set(self._scope, self.key, focus)
            return self.serialize()

        if self.edit_mode:
            if action == "add_step":
                self._push_undo()
                return self._add_step(body)
            elif action == "remove_step":
                self._push_undo()
                return self._remove_step(body)
            elif action == "move_step":
                self._push_undo()
                return self._move_step(body)
            elif action == "toggle_editable":
                self._push_undo()
                return self._toggle_editable(body)

        return self.serialize()

    # --- Serialization ---

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "active_step": self.active_key,
            "progress": [
                {"key": ef.key, "label": ef.effective_label,
                 "complete": ef.is_complete}
                for ef in self.steps
            ],
        }

    def _serialize_full(self) -> dict:
        state = super()._serialize_full()
        active = self.active_step
        state["eigenform"] = active.serialize() if active else None
        return state

    def get_affordances(self) -> list[Affordance]:
        return self._nav_affordances()

    # --- Rendering ---

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html

        if data.get("edit_mode"):
            html = self._render_edit_header(data)
            html += self._render_edit_steps(data)
        else:
            html = f'<h3>{escape(data["label"])}</h3>'
            if data.get("instruction"):
                html += f'<p>{escape(data["instruction"])}</p>'
            html += self._render_progress_bar(data)

        # Active step content
        active = self.active_step
        if active:
            html += active.render()

        # Remaining affordances
        html += '<div style="margin-top: 12px;">'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'
        return html

    def _render_progress_bar(self, data: dict) -> str:
        """Render the standard progress bar (execution mode)."""
        from engine.affordances import render_affordance_html
        active_key = data.get("active_step")
        progress = data.get("progress", [])
        affs = data.get("affordances", [])

        html = '<div style="margin-bottom: 8px;">'
        for step in progress:
            if step["complete"] and step["key"] != active_key:
                for aff in affs:
                    if aff.get("body", {}).get("focus") == step["key"]:
                        html += render_affordance_html(aff)
                        break
            elif step["key"] == active_key:
                html += (
                    f'<span style="font-weight: bold; margin-right: 4px;'
                    f' padding: 2px 8px; border-bottom: 2px solid #333;">'
                    f'{escape(step["label"])}</span>'
                )
            else:
                html += (
                    f'<span style="margin-right: 4px; padding: 2px 8px;'
                    f' color: #aaa;">{escape(step["label"])}</span>'
                )
        # Continue button
        for aff in affs:
            if aff.get("body", {}).get("action") == "continue" and not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'
        return html

    def _render_edit_header(self, data: dict) -> str:
        """Render label and instruction as inline editable inputs."""
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

    def _render_edit_steps(self, data: dict) -> str:
        """Render step list with add toolbar and per-step controls."""
        from engine.registry import get_registry
        affs = data.get("affordances", [])
        url = self.url

        # Mark structural affordances as rendered
        for aff in affs:
            body = aff.get("body", {})
            action = body.get("action", "")
            if action in ("add_step", "remove_step", "move_step",
                          "toggle_editable", "continue"):
                Eigenform.mark_rendered(aff)
            elif "focus" in body:
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
            f"var b={{action:'add_step',type:this.elements.t.value,"
            f"key:this.elements.k.value,label:this.elements.l.value,config:{{}}}};"
            f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
            f'<div><label style="font-size: 11px; color: #666; display: block;">Type</label>'
            f'<select name="t" style="padding: 4px;">'
            f'<option value="">-- type --</option>{type_options}</select></div>'
            f'<div><label style="font-size: 11px; color: #666; display: block;">Key</label>'
            f'<input name="k" type="text" placeholder="unique-key"'
            f' style="padding: 4px; width: 140px;" /></div>'
            f'<div><label style="font-size: 11px; color: #666; display: block;">Label</label>'
            f'<input name="l" type="text" placeholder="Step Label"'
            f' style="padding: 4px; width: 160px;" /></div>'
            f'<button type="submit" style="padding: 4px 14px; cursor: pointer;'
            f' background: #4a7; color: white; border: 1px solid #396;'
            f' border-radius: 3px;">+ Add</button>'
            f'</form></div>'
        )

        # Step bar with controls
        active_key = data.get("active_step")
        n = len(self.steps)
        html += '<div style="display: flex; flex-wrap: wrap; gap: 2px; margin-bottom: 8px; align-items: center;">'
        for i, ef in enumerate(self.steps):
            key = ef.key
            is_active = key == active_key

            bg = "#fff" if is_active else "#f5f5f5"
            border_bottom = "2px solid #333" if is_active else "2px solid transparent"
            html += (
                f'<div style="display: flex; align-items: center; gap: 2px;'
                f' padding: 4px 6px; background: {bg};'
                f' border: 1px solid #ddd; border-bottom: {border_bottom};'
                f' border-radius: 4px 4px 0 0; font-size: 12px;">'
            )

            # Label
            if is_active:
                html += (
                    f'<span style="font-weight: bold; padding: 0 4px;">'
                    f'{escape(ef.effective_label)}</span>'
                )
            else:
                html += render_inline_button(
                    url, {"focus": key}, escape(ef.effective_label),
                    "cursor: pointer; border: none; background: transparent;"
                    " padding: 0 4px; font-size: 12px; color: #333;"
                    " text-decoration: underline;",
                )

            # Move left/right
            if i > 0:
                html += render_inline_button(
                    url, {"action": "move_step", "key": key, "position": i - 1},
                    "&#9664;",
                    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
                    " width: 18px; height: 18px; font-size: 8px; padding: 0;",
                )
            if i < n - 1:
                html += render_inline_button(
                    url, {"action": "move_step", "key": key, "position": i + 1},
                    "&#9654;",
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
                url, {"action": "toggle_editable", "key": key},
                "&#9998;", edit_style,
            )

            # Remove
            html += render_inline_button(
                url, {"action": "remove_step", "key": key},
                "&#10005;",
                "cursor: pointer; border: 1px solid #dcc; background: #fef8f8;"
                " width: 18px; height: 18px; font-size: 9px; padding: 0; color: #c00;",
            )

            html += '</div>'
        html += '</div>'

        if not self.steps:
            html += (
                '<div style="padding: 24px; text-align: center; color: #999;'
                ' border: 2px dashed #ddd; border-radius: 4px; margin-bottom: 8px;">'
                'No steps yet. Use the toolbar above to add one.</div>'
            )

        return html

    def handle_action(self, key: str, body: dict) -> bool:
        """Route action: focus change goes to self, otherwise to active step."""
        if key == self.key:
            self.handle(body)
            return True
        active = self.active_step
        if active and active.key == key:
            active.handle(body)
            # Clear explicit focus so auto-advance kicks in
            self._store.set(self._scope, self.key, None)
            return True
        return False
