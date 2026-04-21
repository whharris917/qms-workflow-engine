"""Page — a component that contains and delegates to nested components."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.affordances import (
    Affordance,
    SimpleButtonAffordance,
    SetValueAffordance,
)
from engine.component import Component
from engine.page_mutations import PageMutationsMixin
from engine.store import Store
from engine.templates import render_template


@dataclass
class Page(PageMutationsMixin, Component):
    """A component whose content is other components.

    Page is responsible for rendering itself, but it delegates rendering
    of its nested components to the components themselves. It provides each
    nested component a region and lets them fill it.

    Page is the persistence boundary. Each page owns its own Store
    backed by a separate JSON file (data_dir / "{scope}.json"). Children
    inherit this store via bind().

    When mutable_structure=True (Phase D), the page exposes affordances
    for adding, removing, and reordering components at runtime. Structural
    mutations modify __structure in the store and trigger a live rebuild.
    """
    form = "page"

    components: list[Component] = field(default_factory=list)
    mutable_structure: bool = False

    # Preserved during bind() — unbound seed components for callable matching
    _seed: list[Component] = field(default_factory=list, repr=False)


    @property
    def children(self) -> list[Component]:
        return self.components

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["components"] = [ef.to_descriptor() for ef in self.components]
        return desc

    def bind(self, data_dir_or_store=None, scope: str = "", url_prefix: str = "",
             *, store=None, **kwargs) -> Page:
        """Produce a bound copy of this page and all nested components.

        Unlike other components, Page creates its own Store. This
        makes the page the persistence boundary — one JSON file per page.

        When called as a top-level page, data_dir_or_store is a Path and
        the Store is created at data_dir / "{scope}.json".

        When embedded as a child of another Page, data_dir_or_store
        is the parent's Store. The data directory is derived from the
        parent store's path, and an independent Store is created for the
        embedded page.

        Structural persistence (Phase C): on first bind, the component
        tree is serialized to __structure in the store. On subsequent
        binds, the stored structure is read and used to reconstruct the
        tree — matching seed components by key to preserve callables.
        If the stored structure is missing or corrupt, falls back to
        the Python seed definition.
        """
        import copy
        from engine.registry import from_descriptor, get_registry

        if store is not None:
            data_dir_or_store = store
        embedded = isinstance(data_dir_or_store, Store)
        if embedded:
            # Embedded: derive data_dir from parent store, use own key for isolation
            data_dir = data_dir_or_store.path.parent
            store = Store(data_dir / f"{scope}__{self.key}.json")
            # Nest URL under parent's prefix
            url_prefix = f"{url_prefix}/{self.key}"
        else:
            data_dir = data_dir_or_store
            store = Store(data_dir / f"{scope}.json")
        bound = copy.deepcopy(self)
        bound._store = store
        bound._scope = scope
        bound._url_prefix = url_prefix

        # Preserve unbound seed for _rebuild() callable matching
        bound._seed = list(bound.components)

        # --- Structural persistence ---
        # __structure is stored at scope=self.key (matching the convention
        # used by Navigation/Group) so that children — bound at
        # scope=self.key — can locate their own descriptor entry via
        # self._scope and mutate it through _set_my_field/_set_my_config.
        stored_structure = store.get(bound.key, "__structure")

        if stored_structure is None:
            # First bind: write seed structure to store
            structure = [ef.to_descriptor() for ef in bound._seed]
            if bound.mutable_structure:
                for desc in structure:
                    desc["editable"] = True
            store.set(bound.key, "__structure", structure)
            source = bound._seed
        else:
            # Subsequent bind: reconstruct from stored structure
            # Fall back to seed if stored structure is corrupted
            try:
                source = bound._reconstruct(stored_structure)
            except Exception:
                store.delete(bound.key, "__structure")
                source = bound._seed

        bound.components = [
            ef.bind(store=store, scope=bound.key, url_prefix=url_prefix)
            for ef in source
        ]

        bound._validate_sibling_refs()

        return bound

    def _validate_sibling_refs(self):
        """Walk the bound tree and validate every SiblingRef resolves.

        A SiblingRef(key, expects=cls) is valid if:
          1. A component with key=`key` exists in the same scope as the
             declaring component (its parent container).
          2. If `expects` is set, that sibling is an instance of `cls`.

        Raises SiblingRefError on the first unresolved reference. The error
        message names the declaring component, the scope, the missing key,
        and the sibling keys that do exist — actionable diagnostics for the
        usual cause (sibling renamed or deleted without updating dependents).

        Call site: Page.bind(), after children are bound. This closes
        the silent-orphan bug where a renamed sibling would leave its
        dependents quietly broken.
        """
        from engine.sibling_ref import SiblingRef, SiblingRefError

        # Build scope -> {key: component} map by walking the bound tree.
        # Only include components with a scope (bound ones).
        scope_map: dict[str, dict[str, "Component"]] = {}

        def _walk(ef):
            scope = getattr(ef, "_scope", None)
            if scope is not None:
                scope_map.setdefault(scope, {})[ef.key] = ef
            for child in ef.children:
                _walk(child)

        _walk(self)

        # Now walk again and validate each component's sibling refs.
        def _validate(ef):
            refs = ef._sibling_refs()
            if refs:
                scope = getattr(ef, "_scope", None)
                siblings = scope_map.get(scope, {}) if scope is not None else {}
                for ref in refs:
                    if ref.key not in siblings:
                        raise SiblingRefError(
                            owner_key=ef.key,
                            owner_scope=str(scope) if scope is not None else "(unbound)",
                            ref=ref,
                            known_keys=sorted(siblings.keys()),
                            reason="missing",
                        )
                    if ref.expects is not None:
                        actual = siblings[ref.key]
                        if not isinstance(actual, ref.expects):
                            raise SiblingRefError(
                                owner_key=ef.key,
                                owner_scope=str(scope) if scope is not None else "(unbound)",
                                ref=ref,
                                known_keys=sorted(siblings.keys()),
                                reason="type_mismatch",
                                actual_type=type(actual),
                            )
            for child in ef.children:
                _validate(child)

        _validate(self)

    def _reconstruct(self, stored_structure: list[dict]) -> list[Component]:
        """Reconstruct component list from stored descriptors + seed."""
        from engine.registry import from_descriptor, get_registry

        seed_by_key = {ef.key: ef for ef in self._seed}
        reg = get_registry()
        return [
            from_descriptor(desc, reg, seed=seed_by_key.get(desc.get("key")))
            for desc in stored_structure
        ]

    def _rebuild(self):
        """Reconstruct the live component tree from __structure.

        Called after structural mutations (add/remove/move) to refresh
        the bound component list from the updated stored structure.
        """
        stored = self._store.get(self.key, "__structure")
        if stored is None:
            return
        try:
            source = self._reconstruct(stored)
        except Exception:
            self._store.delete(self.key, "__structure")
            source = self._seed
        self.components = [
            ef.bind(store=self._store, scope=self.key, url_prefix=self._url_prefix)
            for ef in source
        ]

    def _rebuild_from_seed(self) -> dict:
        """Discard all structural changes and restore the original seed definition.

        Clears all stored data (values and structure), rewrites __structure
        from the seed, and rebinds from the seed components.
        """
        # Clear everything
        self._store.clear_scope(self._scope)
        self._store.clear_scope(self.key)
        self._clear_recursive(self.components)

        # Rewrite structure from seed
        structure = [ef.to_descriptor() for ef in self._seed]
        if self.mutable_structure:
            for desc in structure:
                desc["editable"] = True
        self._store.set(self.key, "__structure", structure)

        # Rebind from seed
        self.components = [
            ef.bind(store=self._store, scope=self.key, url_prefix=self._url_prefix)
            for ef in self._seed
        ]
        return self.serialize()

    def _get_feedback(self) -> dict:
        """Read the feedback structure from the store."""
        fb = self._store.get(self._scope, "__feedback") if self._store else None
        if fb and isinstance(fb, dict) and "errors" in fb:
            return fb
        return {"errors": {}, "success": None}

    def _set_feedback(self, status: str, message: str, target: str | None = None):
        now = datetime.datetime.now().isoformat(timespec="seconds")
        fb = self._get_feedback()

        if target is None:
            # Page-level action: fresh start
            fb = {"errors": {}, "success": None}
            if status == "error":
                fb["errors"]["__page"] = {"message": message, "timestamp": now}
            else:
                fb["success"] = {"message": message, "timestamp": now}
        elif status == "error":
            fb["success"] = None  # Error replaces previous success
            fb["errors"][target] = {"message": message, "timestamp": now}
        else:
            fb["errors"].pop(target, None)  # Success clears error for this target
            fb["success"] = {"message": message, "target": target, "timestamp": now}

        self._store.set(self._scope, "__feedback", fb)

    def _dismiss_feedback(self, target: str):
        """Remove a specific error from the feedback."""
        fb = self._get_feedback()
        fb["errors"].pop(target, None)
        self._store.set(self._scope, "__feedback", fb)

    _PAGE_ACTION_MESSAGES = {
        "reset": "Page reset.",
        "rebuild_from_seed": "Rebuilt from seed definition.",
    }

    def handle(self, body: dict) -> dict:
        """Handle a page-level action, capturing feedback."""
        result = super().handle(body)
        action = body.get("action", "")
        if "error" in result:
            self._set_feedback("error", result["error"])
        elif action in self._PAGE_ACTION_MESSAGES:
            self._set_feedback("success", self._PAGE_ACTION_MESSAGES[action])
        elif action == "add_component":
            self._set_feedback("success", f"Added {body.get('label', body.get('type', '?'))} ({body.get('key', '?')}).")
        elif action == "remove_component":
            self._set_feedback("success", f"Removed '{body.get('key', '?')}'.")
        elif action == "move_component":
            self._set_feedback("success",
                               f"Moved '{body.get('key', '?')}' to position {body.get('position', '?')}.")
        elif action == "toggle_editable":
            self._set_feedback("success",
                               f"Toggled editability for '{body.get('key', '?')}'.")
        elif action == "clear":
            self._set_feedback("success", "Page cleared.")
        return result

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.components)

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "mutable_structure": self.mutable_structure,
        }

    def get_affordances(self) -> list[Affordance]:
        affs = []

        # Dismiss affordances for active errors
        fb = self._get_feedback()
        for target in fb["errors"]:
            affs.append(SimpleButtonAffordance(
                label=f"Dismiss error ({target})",
                method="POST",
                url=self._url_prefix,
                body={"action": "dismiss_feedback", "target": target},
                instruction=f"Dismiss the error for '{target}'.",
            ))

        affs.append(SimpleButtonAffordance(
                label="Reset Page",
                method="POST",
                url=self._url_prefix,
                body={"action": "reset"},
                instruction="Clear all state on this page.",
            )
        )

        if self.mutable_structure:
            from engine.registry import get_type_catalog
            from engine.affordances import AddComponentAffordance

            # Build structured catalog for agent JSON
            catalog = get_type_catalog()
            catalog_dict = {}
            for cat in catalog:
                heading = f"{cat['name']} \u2014 {cat['hint']}"
                catalog_dict[heading] = {
                    t: desc for t, _icon, desc in cat["types"]
                }

            affs.append(AddComponentAffordance(
                label="Add Component",
                method="POST",
                url=self._url_prefix,
                body={
                    "action": "add_component",
                    "type": "<type>",
                    "key": "<optional - auto-generated from type if omitted>",
                    "label": "<optional - auto-generated from type if omitted>",
                },
                instruction=(
                    "Add a new component to this page. Only 'type' is required "
                    "— key and label are auto-generated if omitted. After adding, "
                    "use edit mode to configure type-specific settings."
                ),
                type_catalog=catalog_dict,
            ))

            keys = [ef.key for ef in self.components]
            if keys:
                affs.append(SetValueAffordance(
                    label="Remove Component",
                    method="POST",
                    url=self._url_prefix,
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
                    url=self._url_prefix,
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

            if len(keys) >= 2:
                affs.append(SetValueAffordance(
                    label="Group Components",
                    method="POST",
                    url=self._url_prefix,
                    body={
                        "action": "group_components",
                        "keys": ["<key1>", "<key2>"],
                        "group_key": "<group_key>",
                        "group_label": "<group_label>",
                    },
                    instruction=(
                        f"Wrap two or more components in a new Group. "
                        f"The group replaces them at the first selected position. "
                        f"Available keys: {', '.join(keys)}."
                    ),
                ))

            if keys:
                editable_keys = [ef.key for ef in self.components if ef.editable]
                locked_keys = [ef.key for ef in self.components if not ef.editable]
                parts = []
                if editable_keys:
                    parts.append(f"Editable: {', '.join(editable_keys)}")
                if locked_keys:
                    parts.append(f"Locked: {', '.join(locked_keys)}")
                affs.append(SetValueAffordance(
                    label="Toggle Editable",
                    method="POST",
                    url=self._url_prefix,
                    body={"action": "toggle_editable", "key": "<key>"},
                    instruction=(
                        f"Toggle whether a component is editable. "
                        f"Valid keys: {', '.join(keys)}. {'. '.join(parts)}."
                    ),
                ))

            affs.append(SimpleButtonAffordance(
                label="Rebuild from Seed",
                method="POST",
                url=self._url_prefix,
                body={"action": "rebuild_from_seed"},
                instruction="Discard all structural changes and restore the original page definition. Clears all data.",
            ))

        return affs

    def _serialize_full(self) -> dict:
        state = self._serialize_state()
        fb = self._get_feedback()
        if fb["errors"] or fb["success"]:
            state["feedback"] = {
                "errors": [
                    {"target": t, **v} for t, v in fb["errors"].items()
                ],
                "success": fb["success"],
            }
        page_affs = [a.serialize() for a in self.get_affordances()]
        child_dicts = [s for ef in self.components
                       if (s := ef._serialize_full()) is not None]
        self._float_affordances(child_dicts, page_affs)
        # Strip agent-facing render noise from children, but keep
        # "form" and "key" — themes read these to pick per-type idioms.
        for d in child_dicts:
            for aff in d.get("affordances", []):
                aff.pop("render_hints", None)
                aff.pop("_chrome_rendered", None)
        state["components"] = child_dicts
        state["complete"] = self.is_complete
        state["affordances"] = page_affs
        return state

    def _float_affordances(self, child_dicts: list[dict],
                           page_affs: list[dict]) -> None:
        """Collect floatable affordances from the full component tree."""
        merge_groups: dict[str, dict] = {}
        self._collect_floatable(child_dicts, merge_groups)

        _MERGED_INSTRUCTIONS = {
            "clear": "Clear all data from the target component.",
            "edit": "Switch the target component to edit mode.",
            "batch": (
                "Execute multiple actions on the target component. "
                "Actions run sequentially; execution stops on first error."
            ),
        }
        for fkey, group in merge_groups.items():
            template = group["template"]
            targets = group["targets"]
            merged = {
                "label": template["label"],
                "method": template["method"],
                "body": template["body"],
                "targets": {url: label for url, label in targets},
                "instruction": _MERGED_INSTRUCTIONS.get(fkey, template.get("instruction", "")),
                "_chrome_rendered": True,
            }
            page_affs.append(merged)

    def _collect_floatable(self, dicts: list[dict],
                           merge_groups: dict[str, dict]) -> None:
        """Recursively walk component dicts, extracting floatable affordances."""
        for ef_dict in dicts:
            ef_label = ef_dict.get("label", "")
            # Extract floatable affordances from this node
            remaining = []
            for aff in ef_dict.get("affordances", []):
                fkey = aff.pop("_floatable", None)
                if fkey is not None:
                    aff.pop("render_hints", None)
                    if fkey not in merge_groups:
                        merge_groups[fkey] = {"template": aff, "targets": []}
                    merge_groups[fkey]["targets"].append((aff["url"], ef_label))
                else:
                    remaining.append(aff)
            ef_dict["affordances"] = remaining
            # Recurse into nested components
            if isinstance(ef_dict.get("component"), dict):
                self._collect_floatable([ef_dict["component"]], merge_groups)
            if isinstance(ef_dict.get("components"), list):
                self._collect_floatable(ef_dict["components"], merge_groups)
            if isinstance(ef_dict.get("sections"), dict):
                nested = [s["component"] for s in ef_dict["sections"].values()
                          if isinstance(s, dict) and isinstance(s.get("component"), dict)]
                self._collect_floatable(nested, merge_groups)

    def render_from_data(self, data: dict) -> str:
        from engine.registry import get_type_catalog
        children_html = [ef.render_safely() for ef in self.components]
        child_items = []
        tile_items = []
        type_catalog = []
        if self.mutable_structure:
            type_catalog = get_type_catalog()
            # Build icon/css lookup from catalog
            _icon_map = {}
            _css_map = {}
            for cat in type_catalog:
                for tname, icon, _desc in cat["types"]:
                    _icon_map[tname] = icon
                    _css_map[tname] = cat["css"]

            def _build_tile(ef, idx):
                from engine.component import Component as EF
                tile = {
                    "key": ef.key,
                    "index": idx,
                    "type": ef.form,
                    "label": ef.label or ef.key,
                    "icon": _icon_map.get(ef.form, "?"),
                    "css": _css_map.get(ef.form, ""),
                    "children": [],
                    "is_container": ef.form in EF._CONTAINER_FORMS,
                }
                for ci, child in enumerate(ef.children):
                    tile["children"].append(_build_tile(child, ci))
                return tile

            for i, ef in enumerate(self.components):
                child_items.append({"key": ef.key, "index": i, "html": ef.render_safely(), "editable": ef.editable})
                tile_items.append(_build_tile(ef, i))
        return render_template("page.html", data=data, ef=self, url=self._url_prefix, label=data.get("label", ""), instruction=data.get("instruction") or "", children_html=children_html, child_items=child_items, tile_items=tile_items, type_catalog=type_catalog, feedback=data.get("feedback"), mutable=self.mutable_structure)

    def find_component(self, path: str) -> Component | None:
        """Find a component by its path (e.g., 'tabs/title')."""
        segments = path.split("/")
        children = self.components
        for segment in segments:
            match = next((ef for ef in children if ef.key == segment), None)
            if match is None:
                return None
            if segment == segments[-1]:
                return match
            children = match.children
        return None

    def _clear_recursive(self, components: list[Component]):
        """Clear state for all components, recursing via children property."""
        for ef in components:
            if ef._scope:
                self._store.clear_scope(ef._scope)
            self._clear_recursive(ef.children)

    # --- Structural mutation helpers ---

    def _get_structure(self) -> list[dict]:
        return list(self._store.get(self.key, "__structure") or [])

    def _save_structure(self, structure: list[dict]):
        self._store.set(self.key, "__structure", structure)

    _actions = {
        "dismiss_feedback": "_do_dismiss_feedback",
        "reset": "_do_reset",
        "rebuild_from_seed": "_do_rebuild_from_seed",
        "add_component": "_do_add_component",
        "remove_component": "_do_remove_component",
        "move_component": "_do_move_component",
        "toggle_editable": "_do_toggle_editable",
        "group_components": "_do_group_components",
        "reparent_component": "_do_reparent_component",
        "ungroup_component": "_do_ungroup_component",
    }

    def _do_dismiss_feedback(self, body: dict) -> dict:
        target = body.get("target", "")
        self._dismiss_feedback(target)
        return self.serialize()

    def _do_reset(self, body: dict) -> dict:
        if self.mutable_structure:
            self._store.clear_scope(self._scope)
            self._store.clear_scope(self.key)
            self._clear_recursive(self.components)
            self._rebuild()
        else:
            structure = self._store.get(self.key, "__structure")
            self._store.clear_scope(self._scope)
            self._store.clear_scope(self.key)
            self._clear_recursive(self.components)
            if structure is not None:
                self._store.set(self.key, "__structure", structure)
        return self.serialize()

    # Structural mutation methods (_do_rebuild_from_seed, _do_add_component,
    # _add_component, _remove_component, _move_component, _group_components,
    # _ungroup_component, _reparent_component, handle_action, and tree helpers)
    # are provided by PageMutationsMixin in engine/page_mutations.py.
