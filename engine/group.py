"""Group — a named container for reusable component compositions.

The simplest container: holds children, renders them, has identity.
No collapse, no tabs, no sequencing. Just grouping with a name.

Use Group to define reusable named compositions:

    # Define once
    address = Group(key="address", label="Address", components=[
        TextForm(key="street", label="Street"),
        TextForm(key="city", label="City"),
        ChoiceForm(key="country", label="Country", options=["US", "UK", "DE"]),
    ])

    # Use in multiple pages
    Page(key="shipping", components=[address, ...])
    Page(key="billing", components=[address, ...])

For parameterized compositions, subclass Group:

    class Address(Group):
        def __init__(self, key: str, countries: list[str] = None):
            super().__init__(key=key, label="Address", components=[
                TextForm(key="street", label="Street"),
                TextForm(key="city", label="City"),
                ChoiceForm(key="country", label="Country",
                           options=countries or ["US", "UK", "DE"]),
            ])

    Page(key="page", components=[
        Address("home", countries=["US", "CA", "MX"]),
        Address("work"),
    ])

bind() deepcopies the Group, so the same definition can safely
appear in multiple pages.

Edit mode (when editable=True): exposes structural operations —
add, remove, and reorder components within the group. Structure is
persisted to the store so changes survive rebinds. Undo/discard
restore the full children scope (structure + data).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.affordances import (
    Affordance,
    SetValueAffordance,
    SimpleButtonAffordance,
)
from engine.component import Component
from engine.store import Store
from engine.templates import render_template


@dataclass
class Group(Component):
    """A named group of components. The simplest container."""
    form = "group"

    components: list[Component] = field(default_factory=list)

    # Preserved during bind — unbound seed components for callable matching
    _seed: list[Component] = field(default_factory=list, repr=False)

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["components"] = [ef.to_descriptor() for ef in self.components]
        return desc

    @property
    def children(self) -> list[Component]:
        return self.components

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.components)

    def _bind_children(self, store: Store, url_prefix: str):
        self._seed = list(self.components)

        # __structure is the on-disk source of truth for child structure
        # AND for child seed-time field overrides (label, instruction, config).
        # Always write it so children's _set_my_field/_set_my_config calls
        # have a descriptor entry to mutate, regardless of editability.
        stored = store.get(self.key, "__structure")
        if stored is None:
            structure = [ef.to_descriptor() for ef in self._seed]
            store.set(self.key, "__structure", structure)
            source = self._seed
        else:
            source = self._reconstruct(stored)

        self.components = [
            ef.bind(store=store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
            for ef in source
        ]

    def _reconstruct(self, stored_structure: list[dict]) -> list[Component]:
        """Reconstruct component list from stored descriptors + seed.

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
        """Reconstruct the live component tree from __structure."""
        stored = self._store.get(self.key, "__structure")
        if stored is None:
            return
        source = self._reconstruct(stored)
        self.components = [
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
            label="Add Component",
            method="POST",
            url=self.url,
            body={
                "action": "add_component",
                "type": "<type>",
                "key": "<unique_key>",
                "label": "<label>",
                "config": {},
                "after": "<sibling_key | null>",
            },
            instruction=(
                f"Add a new component to this group. "
                f"Available types: {', '.join(available)}. "
                f"'after' places it after the named sibling (null = append to end). "
                f"'config' is type-specific. Common examples: "
                f"text/memo/boolean/date: {{}} (no config needed), "
                f"choice: {{\"options\": [\"A\", \"B\"]}}, "
                f"checkbox: {{\"items\": [\"X\", \"Y\"]}}, "
                f"number: {{\"min\": 0, \"max\": 100, \"step\": 1}}, "
                f"list: {{\"fixed_items\": [\"a\", \"b\"]}}. "
                f"GET /types for full config schema per type."
            ),
        ))

        keys = [ef.key for ef in self.components]
        if keys:
            affs.append(SetValueAffordance(
                label="Remove Component",
                method="POST",
                url=self.url,
                body={"action": "remove_component", "key": "<key>"},
                instruction=(
                    f"Remove a component and its data. "
                    f"Valid keys: {', '.join(keys)}."
                ),
            ))

        if len(keys) > 1:
            affs.append(SetValueAffordance(
                label="Move Component",
                method="POST",
                url=self.url,
                body={
                    "action": "move_component",
                    "key": "<key>",
                    "position": "<index>",
                },
                instruction=(
                    f"Move a component to a new position (0-based index). "
                    f"Current order: {', '.join(keys)}."
                ),
            ))

        if keys:
            editable_status = ", ".join(
                f"{ef.key}={'on' if ef.editable else 'off'}"
                for ef in self.components
            )
            affs.append(SetValueAffordance(
                label="Toggle Editable",
                method="POST",
                url=self.url,
                body={"action": "toggle_editable", "key": "<key>"},
                instruction=(
                    f"Toggle editability of a component. "
                    f"Valid keys: {', '.join(keys)}. "
                    f"Current state: {editable_status}."
                ),
            ))

        return affs

    # --- Structural mutation handlers ---

    def _clear_component_data(self, ef: Component):
        """Surgically clear stored data for one component and its children."""
        if ef._store and ef._scope:
            ef._store.delete(ef._scope, ef.key)
        for child in ef.children:
            if child._scope and child._scope != ef._scope:
                self._store.clear_scope(child._scope)
            self._clear_component_data(child)

    def _add_component(self, body: dict) -> dict:
        from engine.registry import get_registry, validate_config

        type_name = body.get("type")
        key = body.get("key")
        label = body.get("label", key)
        config = body.get("config", {})
        after = body.get("after")

        if not type_name or not key:
            return self._error("Both 'type' and 'key' are required.",
                               action="add_component")

        reg = get_registry()
        if type_name not in reg:
            return self._error(
                f"Unknown type: {type_name}. "
                f"Available: {', '.join(reg.available())}",
                action="add_component")

        existing_keys = {ef.key for ef in self.components}
        if key in existing_keys:
            return self._error(f"Key '{key}' already exists.",
                               action="add_component")

        # Validate config before persisting
        if config:
            err = validate_config(type_name, config, reg)
            if err:
                return self._error(err, action="add_component")

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
                                   action="add_component")
            structure.insert(idx + 1, desc)
        else:
            structure.append(desc)

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _remove_component(self, body: dict) -> dict:
        key = body.get("key")
        if not key:
            return self._error("'key' is required.", action="remove_component")

        ef = next((e for e in self.components if e.key == key), None)
        if ef is None:
            return self._error(f"Component '{key}' not found.",
                               action="remove_component")

        self._clear_component_data(ef)

        structure = self._get_structure()
        structure = [d for d in structure if d["key"] != key]
        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _move_component(self, body: dict) -> dict:
        key = body.get("key")
        position = body.get("position")

        if not key:
            return self._error("'key' is required.", action="move_component")
        if position is None:
            return self._error("'position' is required.",
                               action="move_component")

        try:
            position = int(position)
        except (TypeError, ValueError):
            return self._error(f"Invalid position: {position}",
                               action="move_component")

        structure = self._get_structure()
        idx = next((i for i, d in enumerate(structure)
                    if d["key"] == key), None)
        if idx is None:
            return self._error(f"Component '{key}' not found.",
                               action="move_component")

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
            return self._error(f"Component '{key}' not found.",
                               action="toggle_editable")

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    _actions = {
        "add_component": "_do_add_component",
        "remove_component": "_do_remove_component",
        "move_component": "_do_move_component",
        "toggle_editable": "_do_toggle_editable",
    }

    def _do_add_component(self, body: dict) -> dict:
        if not self.edit_mode:
            return self.serialize()
        self._push_undo()
        return self._add_component(body)

    def _do_remove_component(self, body: dict) -> dict:
        if not self.edit_mode:
            return self.serialize()
        self._push_undo()
        return self._remove_component(body)

    def _do_move_component(self, body: dict) -> dict:
        if not self.edit_mode:
            return self.serialize()
        self._push_undo()
        return self._move_component(body)

    def _do_toggle_editable(self, body: dict) -> dict:
        if not self.edit_mode:
            return self.serialize()
        self._push_undo()
        return self._toggle_editable(body)

    # --- Serialization ---

    def _serialize_state(self) -> dict:
        return self._base_state()

    def _serialize_full(self) -> dict:
        state = super()._serialize_full()
        state["components"] = [
            s for ef in self.components if (s := ef.serialize()) is not None
        ]
        return state

    def get_affordances(self):
        return []

    # --- Rendering ---

    def render_from_data(self, data: dict) -> str:
        from engine.registry import get_registry
        children_html = [ef.render_safely() for ef in self.components]
        child_items = []
        if data.get("edit_mode"):
            for i, ef in enumerate(self.components):
                child_items.append({"key": ef.key, "editable": ef.editable, "index": i, "html": ef.render_safely()})
        available_types = sorted(get_registry().available()) if data.get("edit_mode") else []
        return render_template("group.html", data=data, ef=self, url=self.url, label=data.get("label", ""), instruction=data.get("instruction") or "", children_html=children_html, child_items=child_items, available_types=available_types)
