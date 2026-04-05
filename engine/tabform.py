"""TabForm — an eigenform that shows one tab at a time.

Edit mode (when editable=True): exposes structural operations —
add, remove, reorder tabs, and toggle editability on tab content
eigenforms. Structure is persisted to the store so changes survive
rebinds. Faithful projection is maintained: only the active tab's
content appears in both JSON and HTML, regardless of mode.
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
class TabForm(Eigenform):
    """An eigenform with multiple tabs. Only the active tab is visible.

    The active tab is persisted state. Switching tabs is an affordance.
    Both the agent and human see only the active tab's eigenforms —
    faithful projection requires that hidden tabs are absent from
    the serialization.
    """
    tabs: dict[str, Eigenform] = field(default_factory=dict)

    # Preserved during bind — unbound seed tabs for callable matching
    _seed: dict[str, Eigenform] = field(default_factory=dict, repr=False)

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["tabs"] = {k: v.to_descriptor() for k, v in self.tabs.items()}
        return desc

    @property
    def children(self) -> list[Eigenform]:
        return list(self.tabs.values())

    @property
    def active_tab_key(self) -> str:
        """The currently active tab key, from the store."""
        stored = self.value
        if stored and stored in self.tabs:
            return stored
        return next(iter(self.tabs)) if self.tabs else ""

    @property
    def active_tab(self) -> Eigenform | None:
        return self.tabs.get(self.active_tab_key)

    # --- Structural persistence ---

    def _bind_children(self, store: Store, url_prefix: str):
        self._seed = dict(self.tabs)

        if self.editable:
            stored = store.get(self.key, "__structure")
            if stored is None:
                structure = [
                    {"tab_key": k, "eigenform": v.to_descriptor()}
                    for k, v in self._seed.items()
                ]
                store.set(self.key, "__structure", structure)
                source = self._seed
            else:
                source = self._reconstruct(stored)
        else:
            source = self.tabs

        self.tabs = {
            tab_key: ef.bind(store=store, scope=self.key,
                             url_prefix=f"{url_prefix}/{self.key}")
            for tab_key, ef in source.items()
        }

    def _reconstruct(self, stored_structure: list[dict]) -> dict[str, Eigenform]:
        """Reconstruct tabs dict from stored structure + seed."""
        from engine.registry import from_descriptor, get_registry
        seed_by_key = {ef.key: ef for ef in self._seed.values()}
        reg = get_registry()
        result = {}
        for entry in stored_structure:
            tab_key = entry["tab_key"]
            desc = entry["eigenform"]
            ef = from_descriptor(desc, reg, seed=seed_by_key.get(desc.get("key")))
            ef.editable = desc.get("editable", False)
            result[tab_key] = ef
        return result

    def _rebuild(self):
        """Reconstruct the live tabs from __structure."""
        stored = self._store.get(self.key, "__structure")
        if stored is None:
            return
        source = self._reconstruct(stored)
        self.tabs = {
            tab_key: ef.bind(store=self._store, scope=self.key,
                             url_prefix=f"{self._url_prefix}/{self.key}")
            for tab_key, ef in source.items()
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

    def _tab_switch_affordances(self) -> list[Affordance]:
        other_tabs = {
            tab_key: ef.effective_label
            for tab_key, ef in self.tabs.items()
            if tab_key != self.active_tab_key
        }
        if not other_tabs:
            return []
        aff = Affordance(
            label="Switch Tab",
            method="POST",
            url=self.url,
            body={"tab": "<tab_key>"},
            instruction="Switch to a different tab.",
        )
        aff._tabs = other_tabs
        aff._chrome_rendered = True
        return [aff]

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        affs.extend(self._tab_switch_affordances())

        from engine.registry import get_registry
        reg = get_registry()
        available = reg.available()

        affs.append(SetValueAffordance(
            label="Add Tab",
            method="POST",
            url=self.url,
            body={
                "action": "add_tab",
                "tab_key": "<tab_key>",
                "type": "<type>",
                "key": "<eigenform_key>",
                "label": "<label>",
                "config": {},
                "after": "<sibling_tab_key | null>",
            },
            instruction=(
                f"Add a new tab. 'tab_key' is the tab identifier for switching. "
                f"Available types: {', '.join(available)}. "
                f"'after' places it after the named tab (null = append to end). "
                f"'config' is type-specific."
            ),
        ))

        tab_keys = list(self.tabs.keys())
        for tab_key, ef in self.tabs.items():
            affs.append(SimpleButtonAffordance(
                label=f"Remove Tab {tab_key}",
                method="POST",
                url=self.url,
                body={"action": "remove_tab", "tab_key": tab_key},
                instruction=f"Remove the '{tab_key}' tab and its data.",
            ))
            state = "editable" if ef.editable else "not editable"
            affs.append(SimpleButtonAffordance(
                label=f"Toggle Editable {tab_key}",
                method="POST",
                url=self.url,
                body={"action": "toggle_editable", "tab_key": tab_key},
                instruction=f"Toggle editability of '{tab_key}' (currently {state}).",
            ))

        if len(self.tabs) > 1:
            for tab_key in tab_keys:
                affs.append(SetValueAffordance(
                    label=f"Move Tab {tab_key}",
                    method="POST",
                    url=self.url,
                    body={
                        "action": "move_tab",
                        "tab_key": tab_key,
                        "position": "<index>",
                    },
                    instruction=(
                        f"Move '{tab_key}' to a new position (0-based index). "
                        f"Current order: {', '.join(tab_keys)}."
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

    def _add_tab(self, body: dict) -> dict:
        from engine.registry import get_registry

        tab_key = body.get("tab_key")
        type_name = body.get("type")
        key = body.get("key")
        label = body.get("label", key)
        config = body.get("config", {})
        after = body.get("after")

        if not tab_key or not type_name or not key:
            return self._error("'tab_key', 'type', and 'key' are required.",
                               action="add_tab")

        reg = get_registry()
        if type_name not in reg:
            return self._error(
                f"Unknown type: {type_name}. "
                f"Available: {', '.join(reg.available())}",
                action="add_tab")

        if tab_key in self.tabs:
            return self._error(f"Tab key '{tab_key}' already exists.",
                               action="add_tab")

        existing_ef_keys = {ef.key for ef in self.tabs.values()}
        if key in existing_ef_keys:
            return self._error(f"Eigenform key '{key}' already exists.",
                               action="add_tab")

        desc = {"type": type_name, "key": key, "label": label, "editable": True}
        if body.get("instruction"):
            desc["instruction"] = body["instruction"]
        if config:
            desc["config"] = config

        structure = self._get_structure()
        entry = {"tab_key": tab_key, "eigenform": desc}
        if after:
            idx = next((i for i, e in enumerate(structure)
                        if e["tab_key"] == after), None)
            if idx is None:
                return self._error(f"Tab '{after}' not found.",
                                   action="add_tab")
            structure.insert(idx + 1, entry)
        else:
            structure.append(entry)

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _remove_tab(self, body: dict) -> dict:
        tab_key = body.get("tab_key")
        if not tab_key:
            return self._error("'tab_key' is required.", action="remove_tab")

        ef = self.tabs.get(tab_key)
        if ef is None:
            return self._error(f"Tab '{tab_key}' not found.",
                               action="remove_tab")

        self._clear_eigenform_data(ef)

        structure = self._get_structure()
        structure = [e for e in structure if e["tab_key"] != tab_key]
        self._save_structure(structure)

        # If the removed tab was active, reset to first tab
        if self.active_tab_key == tab_key:
            self._store.delete(self._scope, self.key)

        self._rebuild()
        return self.serialize()

    def _move_tab(self, body: dict) -> dict:
        tab_key = body.get("tab_key")
        position = body.get("position")

        if not tab_key:
            return self._error("'tab_key' is required.", action="move_tab")
        if position is None:
            return self._error("'position' is required.", action="move_tab")

        try:
            position = int(position)
        except (TypeError, ValueError):
            return self._error(f"Invalid position: {position}",
                               action="move_tab")

        structure = self._get_structure()
        idx = next((i for i, e in enumerate(structure)
                    if e["tab_key"] == tab_key), None)
        if idx is None:
            return self._error(f"Tab '{tab_key}' not found.",
                               action="move_tab")

        entry = structure.pop(idx)
        position = max(0, min(position, len(structure)))
        structure.insert(position, entry)

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _toggle_editable(self, body: dict) -> dict:
        tab_key = body.get("tab_key")
        if not tab_key:
            return self._error("'tab_key' is required.",
                               action="toggle_editable")

        structure = self._get_structure()
        found = False
        for entry in structure:
            if entry["tab_key"] == tab_key:
                desc = entry["eigenform"]
                desc["editable"] = not desc.get("editable", False)
                found = True
                break

        if not found:
            return self._error(f"Tab '{tab_key}' not found.",
                               action="toggle_editable")

        self._save_structure(structure)
        self._rebuild()
        return self.serialize()

    def _handle(self, body: dict) -> dict:
        """Handle tab switch and structural actions."""
        action = body.get("action", "")

        # Tab switching works in both modes
        tab_key = body.get("tab")
        if tab_key and tab_key in self.tabs:
            self._store.set(self._scope, self.key, tab_key)
            return self.serialize()

        if self.edit_mode:
            if action == "add_tab":
                self._push_undo()
                return self._add_tab(body)
            elif action == "remove_tab":
                self._push_undo()
                return self._remove_tab(body)
            elif action == "move_tab":
                self._push_undo()
                return self._move_tab(body)
            elif action == "toggle_editable":
                self._push_undo()
                return self._toggle_editable(body)

        return self.serialize()

    # --- Serialization ---

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "active_tab": self.active_tab_key,
            "tab_keys": list(self.tabs.keys()),
        }

    def _serialize_full(self) -> dict:
        state = super()._serialize_full()
        active = self.active_tab
        state["eigenform"] = active.serialize() if active else None
        return state

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.tabs.values())

    def get_affordances(self) -> list[Affordance]:
        return self._tab_switch_affordances()

    # --- Rendering ---

    def render_from_data(self, data: dict) -> str:
        from engine.registry import get_registry
        active_key = data.get("active_tab", "")
        tab_items = []
        for i, tab_key in enumerate(data.get("tab_keys", [])):
            ef = self.tabs.get(tab_key)
            tab_items.append({"key": tab_key, "label": ef.effective_label if ef else tab_key, "is_active": tab_key == active_key, "editable": ef.editable if ef else False, "index": i})
        active = self.active_tab
        active_html = active.render() if active else ""
        available_types = sorted(get_registry().available()) if data.get("edit_mode") else []
        return render_template("tab.html", data=data, ef=self, url=self.url, label=data.get("label", ""), instruction=data.get("instruction") or "", active_tab_key=active_key, tab_items=tab_items, active_html=active_html, available_types=available_types)

    def handle_action(self, key: str, body: dict) -> bool:
        """Route action: tab switch goes to self, otherwise to active tab.
        Returns True if the action was handled."""
        if key == self.key:
            self.handle(body)
            return True
        active = self.active_tab
        if active and active.key == key:
            active.handle(body)
            return True
        return False
