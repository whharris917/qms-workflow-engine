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

from engine.affordances import (
    Affordance,
    SetValueAffordance,
    SimpleButtonAffordance,
    SwitchTabAffordance,
)
from engine.eigenform import Eigenform
from engine.store import Store
from engine.templates import render_template


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
        from engine.registry import get_registry
        active_key = data.get("active_step")
        step_items = []
        for i, ef in enumerate(self.steps):
            step_items.append({"key": ef.key, "label": ef.effective_label, "is_active": ef.key == active_key, "editable": ef.editable, "index": i, "complete": ef.is_complete})
        active = self.active_step
        active_html = active.render() if active else ""
        available_types = sorted(get_registry().available()) if data.get("edit_mode") else []
        return render_template("chain.html", data=data, ef=self, url=self.url, label=data.get("label", ""), instruction=data.get("instruction") or "", active_html=active_html, step_items=step_items, available_types=available_types)

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
