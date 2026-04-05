"""NavigationForm — unified container with four display modes.

Modes:
    tabs:      Free access, one child visible. Classic tabbed interface.
    chain:     Gated access, auto-advance to first incomplete. Wizard.
    sequence:  Gated access, manual Back/Next navigation.
    accordion: Free access, all children visible with expand/collapse.

All modes share: bind, edit mode (add/remove/move/toggle_editable),
structural persistence, snapshot/restore, is_complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.affordances import (
    Affordance,
    SetValueAffordance,
    SimpleButtonAffordance,
)
from engine.eigenform import Eigenform
from engine.store import Store
from engine.templates import render_template


@dataclass
class NavigationForm(Eigenform):
    """A container that presents children in one of four modes."""
    steps: list[Eigenform] = field(default_factory=list)
    mode: str = "sequence"
    default_expanded: bool = True  # accordion mode: initial section state

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

    # --- Active child (single-projection modes) ---

    def _highest_accessible_index(self) -> int:
        if self.mode in ("tabs", "accordion"):
            return len(self.steps) - 1
        for i, ef in enumerate(self.steps):
            if not ef.is_complete:
                return i
        return len(self.steps) - 1

    def _is_accessible(self, index: int) -> bool:
        return index <= self._highest_accessible_index()

    @property
    def _active_key(self) -> str | None:
        stored = self.value
        if stored and isinstance(stored, str) and stored in {ef.key for ef in self.steps}:
            return stored
        return None

    @property
    def active_step(self) -> Eigenform | None:
        if self.mode == "accordion":
            return None
        active_key = self._active_key
        if self.mode == "chain":
            # Explicit focus overrides auto-advance
            if active_key:
                for ef in self.steps:
                    if ef.key == active_key:
                        return ef
            # Auto-advance: first incomplete
            for ef in self.steps:
                if not ef.is_complete:
                    return ef
            return self.steps[-1] if self.steps else None
        # tabs / sequence: validate accessibility
        if active_key:
            for i, ef in enumerate(self.steps):
                if ef.key == active_key and self._is_accessible(i):
                    return ef
        return self.steps[0] if self.steps else None

    @property
    def active_index(self) -> int:
        active = self.active_step
        if active:
            for i, ef in enumerate(self.steps):
                if ef.key == active.key:
                    return i
        return 0

    # --- Accordion expanded state ---

    @property
    def _expanded_state(self) -> dict[str, bool]:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored
        return {}

    def _is_expanded(self, key: str) -> bool:
        return self._expanded_state.get(key, self.default_expanded)

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
        """Navigation affordances — mode-dependent."""
        affordances = []
        url = self.url

        if self.mode == "tabs":
            other = {
                ef.key: ef.effective_label
                for ef in self.steps
                if ef.key != (self.active_step.key if self.active_step else None)
            }
            if other:
                aff = Affordance(
                    label="Switch Tab",
                    method="POST", url=url,
                    body={"step": "<step_key>"},
                    instruction="Switch to a different tab.",
                )
                aff._steps = other
                aff._chrome_rendered = True
                affordances.append(aff)

        elif self.mode == "chain":
            active = self.active_step
            if active and active.is_complete and self._active_key is not None:
                affordances.append(SimpleButtonAffordance(
                    label="Continue",
                    method="POST", url=url,
                    body={"action": "continue"},
                    instruction="Resume from the next incomplete step.",
                ))
            completed = {
                ef.key: ef.effective_label
                for ef in self.steps
                if ef.is_complete
                and ef.key != (active.key if active else None)
            }
            if completed:
                aff = Affordance(
                    label="Back to Step",
                    method="POST", url=url,
                    body={"step": "<step_key>"},
                    instruction="Jump back to a completed step.",
                )
                aff._steps = completed
                aff._chrome_rendered = True
                affordances.append(aff)

        elif self.mode == "sequence":
            idx = self.active_index
            if idx > 0:
                prev = self.steps[idx - 1]
                affordances.append(SimpleButtonAffordance(
                    label=f"\u2190 Back: {prev.effective_label}",
                    method="POST", url=url,
                    body={"step": prev.key},
                    instruction=f"Go back to {prev.effective_label}.",
                ))
            if idx < len(self.steps) - 1 and self.steps[idx].is_complete:
                nxt = self.steps[idx + 1]
                affordances.append(SimpleButtonAffordance(
                    label=f"Next: {nxt.effective_label} \u2192",
                    method="POST", url=url,
                    body={"step": nxt.key},
                    instruction=f"Advance to {nxt.effective_label}.",
                ))
            active = self.active_step
            highest = self._highest_accessible_index()
            completed = {
                ef.key: ef.effective_label
                for i, ef in enumerate(self.steps)
                if i <= highest
                and ef.key != (active.key if active else None)
                and ef.is_complete
            }
            if completed:
                aff = Affordance(
                    label="Go to Step",
                    method="POST", url=url,
                    body={"step": "<step_key>"},
                    instruction="Jump to a completed step.",
                )
                aff._steps = completed
                aff._chrome_rendered = True
                affordances.append(aff)

        elif self.mode == "accordion":
            if self.steps:
                sections = {
                    ef.key: {
                        "label": ef.effective_label,
                        "expanded": self._is_expanded(ef.key),
                    }
                    for ef in self.steps
                }
                aff = Affordance(
                    label="Toggle Section",
                    method="POST", url=url,
                    body={"action": "toggle", "step": "<step_key>"},
                    instruction="Expand or collapse a section.",
                )
                aff._sections = sections
                aff._chrome_rendered = True
                affordances.append(aff)

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
                f"Add a new step. "
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
                instruction=f"Remove '{ef.key}' and its data.",
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

        # If the removed step was active, reset
        if self._active_key == key:
            self._store.delete(self._scope, self.key)

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
        action = body.get("action", "")

        # --- Navigation ---
        if self.mode == "accordion" and action == "toggle":
            step_key = body.get("step")
            if step_key and step_key in {ef.key for ef in self.steps}:
                state = dict(self._expanded_state)
                state[step_key] = not self._is_expanded(step_key)
                self._store.set(self._scope, self.key, state)
            return self.serialize()

        if self.mode == "chain" and action == "continue":
            self._store.set(self._scope, self.key, None)
            return self.serialize()

        step_key = body.get("step")
        if step_key and self.mode != "accordion":
            for i, ef in enumerate(self.steps):
                if ef.key == step_key and self._is_accessible(i):
                    self._store.set(self._scope, self.key, step_key)
                    break
            return self.serialize()

        # --- Structural (edit mode) ---
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
        state = self._base_state()
        state["mode"] = self.mode

        if self.mode == "accordion":
            state["step_keys"] = [ef.key for ef in self.steps]
        else:
            active = self.active_step
            state["active_step"] = active.key if active else None
            progress = []
            highest = self._highest_accessible_index()
            for i, ef in enumerate(self.steps):
                entry = {
                    "key": ef.key,
                    "label": ef.effective_label,
                    "complete": ef.is_complete,
                }
                if self.mode in ("sequence", "chain"):
                    entry["accessible"] = i <= highest
                progress.append(entry)
            state["progress"] = progress

        return state

    def _serialize_full(self) -> dict:
        state = super()._serialize_full()
        if self.mode == "accordion":
            state["sections"] = {}
            for ef in self.steps:
                expanded = self._is_expanded(ef.key)
                entry = {"expanded": expanded}
                if expanded:
                    entry["eigenform"] = ef.serialize()
                state["sections"][ef.key] = entry
        else:
            active = self.active_step
            state["eigenform"] = active.serialize() if active else None
        return state

    def get_affordances(self) -> list[Affordance]:
        return self._nav_affordances()

    # --- Rendering ---

    def render_from_data(self, data: dict) -> str:
        from engine.registry import get_registry

        step_items = []
        if self.mode == "accordion":
            section_html = {}
            for i, ef in enumerate(self.steps):
                expanded = self._is_expanded(ef.key) if not data.get("edit_mode") else self._is_expanded(ef.key)
                step_items.append({
                    "key": ef.key, "label": ef.effective_label,
                    "expanded": expanded, "editable": ef.editable, "index": i,
                })
                if expanded:
                    section_html[ef.key] = ef.render()
            active_html = ""
        else:
            section_html = {}
            active_key = data.get("active_step")
            for i, ef in enumerate(self.steps):
                item = {
                    "key": ef.key, "label": ef.effective_label,
                    "is_active": ef.key == active_key, "editable": ef.editable,
                    "index": i, "complete": ef.is_complete,
                }
                if self.mode in ("sequence", "chain"):
                    item["accessible"] = self._is_accessible(i)
                step_items.append(item)
            active = self.active_step
            active_html = active.render() if active else ""

        available_types = sorted(get_registry().available()) if data.get("edit_mode") else []
        return render_template(
            "navigation.html",
            data=data, ef=self, url=self.url, mode=self.mode,
            label=data.get("label", ""),
            instruction=data.get("instruction") or "",
            step_items=step_items,
            active_html=active_html,
            section_html=section_html,
            available_types=available_types,
        )

    def handle_action(self, key: str, body: dict) -> bool:
        if key == self.key:
            self.handle(body)
            return True
        if self.mode == "accordion":
            # Route to any child
            for ef in self.steps:
                if ef.key == key:
                    ef.handle(body)
                    return True
                if hasattr(ef, 'handle_action') and ef.handle_action(key, body):
                    return True
        else:
            active = self.active_step
            if active and active.key == key:
                active.handle(body)
                # Chain mode: clear focus so auto-advance resumes
                if self.mode == "chain":
                    self._store.set(self._scope, self.key, None)
                return True
        return False
