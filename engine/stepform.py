"""SequenceForm — a gated sequence of eigenforms with manual navigation.

Like ChainForm but without auto-advance. Steps must be completed
in order — step N+1 is only accessible when step N is complete.
The user manually navigates between steps using Next/Back affordances.
Completed steps can always be revisited.

Comparison:
    TabForm:       free access to all tabs, no ordering.
    SequenceForm:  gated sequential access, manual navigation.
    ChainForm:     gated sequential access, auto-advances on completion.

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
class SequenceForm(Eigenform):
    """A gated sequence of eigenforms shown one at a time.

    Navigation rules:
    - Step 0 is always accessible.
    - Step N is accessible when step N-1 is complete.
    - The active step persists across page loads.
    - Completed steps can always be revisited.
    - No auto-advance: the user must explicitly navigate forward.
    """
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

    def _highest_accessible_index(self) -> int:
        for i, ef in enumerate(self.steps):
            if not ef.is_complete:
                return i
        return len(self.steps) - 1

    def _is_accessible(self, index: int) -> bool:
        return index <= self._highest_accessible_index()

    @property
    def _active_key(self) -> str | None:
        stored = self.value
        if stored and stored in {ef.key for ef in self.steps}:
            return stored
        return None

    @property
    def active_step(self) -> Eigenform | None:
        active_key = self._active_key
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
        """Navigation affordances — shared by both modes."""
        affordances = []
        idx = self.active_index
        url = self.url

        if idx > 0:
            prev = self.steps[idx - 1]
            affordances.append(SimpleButtonAffordance(
                label=f"\u2190 Back: {prev.effective_label}",
                method="POST",
                url=url,
                body={"step": prev.key},
                instruction=f"Go back to {prev.effective_label}.",
            ))

        if idx < len(self.steps) - 1 and self.steps[idx].is_complete:
            nxt = self.steps[idx + 1]
            affordances.append(SimpleButtonAffordance(
                label=f"Next: {nxt.effective_label} \u2192",
                method="POST",
                url=url,
                body={"step": nxt.key},
                instruction=f"Advance to {nxt.effective_label}.",
            ))

        active = self.active_step
        highest = self._highest_accessible_index()
        for i, ef in enumerate(self.steps):
            if i <= highest and ef.key != (active.key if active else None):
                if ef.is_complete:
                    affordances.append(SwitchTabAffordance(
                        label=f"Go to {ef.effective_label}",
                        method="POST",
                        url=url,
                        body={"step": ef.key},
                        instruction=f"Jump to completed step: {ef.effective_label}.",
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
                f"Add a new step to this sequence. "
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
        """Handle step navigation or structural actions."""
        action = body.get("action", "")

        # Navigation works in both modes
        step_key = body.get("step")
        if step_key:
            for i, ef in enumerate(self.steps):
                if ef.key == step_key and self._is_accessible(i):
                    self._store.set(self._scope, self.key, step_key)
                    break
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
        active = self.active_step
        highest = self._highest_accessible_index()
        return self._base_state() | {
            "active_step": active.key if active else None,
            "progress": [
                {
                    "key": ef.key,
                    "label": ef.effective_label,
                    "complete": ef.is_complete,
                    "accessible": i <= highest,
                }
                for i, ef in enumerate(self.steps)
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
            step_items.append({"key": ef.key, "label": ef.effective_label, "is_active": ef.key == active_key, "editable": ef.editable, "index": i, "complete": ef.is_complete, "accessible": self._is_accessible(i)})
        active = self.active_step
        active_html = active.render() if active else ""
        available_types = sorted(get_registry().available()) if data.get("edit_mode") else []
        return render_template("step.html", data=data, ef=self, url=self.url, label=data.get("label", ""), instruction=data.get("instruction") or "", active_html=active_html, step_items=step_items, available_types=available_types)
