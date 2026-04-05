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
        if not self.sections:
            return []
        sections = {
            sec_key: {
                "label": ef.effective_label,
                "expanded": self._is_expanded(sec_key),
            }
            for sec_key, ef in self.sections.items()
        }
        aff = Affordance(
            label="Toggle Section",
            method="POST",
            url=self.url,
            body={"action": "toggle", "section": "<section_key>"},
            instruction="Expand or collapse a section.",
        )
        aff._sections = sections
        aff._chrome_rendered = True
        return [aff]

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
        from engine.registry import get_registry
        sections_data = data.get("sections", {})
        section_items = []
        section_html = {}
        for i, sec_key in enumerate(data.get("section_keys", [])):
            ef = self.sections.get(sec_key)
            sec_data = sections_data.get(sec_key, {})
            expanded = sec_data.get("expanded", True) if not data.get("edit_mode") else self._is_expanded(sec_key)
            section_items.append({"key": sec_key, "label": ef.effective_label if ef else sec_key, "expanded": expanded, "editable": ef.editable if ef else False, "index": i})
            if expanded and ef:
                section_html[sec_key] = ef.render()
        available_types = sorted(get_registry().available()) if data.get("edit_mode") else []
        return render_template("accordion.html", data=data, ef=self, url=self.url, label=data.get("label", ""), instruction=data.get("instruction") or "", section_items=section_items, section_html=section_html, available_types=available_types)

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
