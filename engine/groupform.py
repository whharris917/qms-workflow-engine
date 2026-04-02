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
        from engine.registry import get_registry
        children_html = [ef.render() for ef in self.eigenforms]
        child_items = []
        if data.get("edit_mode"):
            for i, ef in enumerate(self.eigenforms):
                child_items.append({"key": ef.key, "editable": ef.editable, "index": i, "html": ef.render()})
        available_types = sorted(get_registry().available()) if data.get("edit_mode") else []
        return render_template("group.html", data=data, ef=self, url=self.url, label=data.get("label", ""), instruction=data.get("instruction") or "", children_html=children_html, child_items=child_items, available_types=available_types)
