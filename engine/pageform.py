"""PageForm — an eigenform that contains and delegates to nested eigenforms."""

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
from engine.eigenform import Eigenform
from engine.store import Store
from engine.templates import render_template


@dataclass
class PageForm(Eigenform):
    """An eigenform whose content is other eigenforms.

    PageForm is responsible for rendering itself, but it delegates rendering
    of its nested eigenforms to the eigenforms themselves. It provides each
    nested eigenform a region and lets them fill it.

    PageForm is the persistence boundary. Each page owns its own Store
    backed by a separate JSON file (data_dir / "{scope}.json"). Children
    inherit this store via bind().

    When mutable_structure=True (Phase D), the page exposes affordances
    for adding, removing, and reordering eigenforms at runtime. Structural
    mutations modify __structure in the store and trigger a live rebuild.
    """
    eigenforms: list[Eigenform] = field(default_factory=list)
    mutable_structure: bool = False

    # Preserved during bind() — unbound seed eigenforms for callable matching
    _seed: list[Eigenform] = field(default_factory=list, repr=False)


    @property
    def children(self) -> list[Eigenform]:
        return self.eigenforms

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["eigenforms"] = [ef.to_descriptor() for ef in self.eigenforms]
        return desc

    def bind(self, data_dir_or_store=None, scope: str = "", url_prefix: str = "",
             *, store=None, **kwargs) -> PageForm:
        """Produce a bound copy of this page and all nested eigenforms.

        Unlike other eigenforms, PageForm creates its own Store. This
        makes the page the persistence boundary — one JSON file per page.

        When called as a top-level page, data_dir_or_store is a Path and
        the Store is created at data_dir / "{scope}.json".

        When embedded as a child of another PageForm, data_dir_or_store
        is the parent's Store. The data directory is derived from the
        parent store's path, and an independent Store is created for the
        embedded page.

        Structural persistence (Phase C): on first bind, the eigenform
        tree is serialized to __structure in the store. On subsequent
        binds, the stored structure is read and used to reconstruct the
        tree — matching seed eigenforms by key to preserve callables.
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
        bound._seed = list(bound.eigenforms)

        # --- Structural persistence ---
        # __structure is stored at scope=self.key (matching the convention
        # used by NavigationForm/GroupForm) so that children — bound at
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

        bound.eigenforms = [
            ef.bind(store=store, scope=bound.key, url_prefix=url_prefix)
            for ef in source
        ]

        bound._validate_sibling_refs()

        return bound

    def _validate_sibling_refs(self):
        """Walk the bound tree and validate every SiblingRef resolves.

        A SiblingRef(key, expects=cls) is valid if:
          1. An eigenform with key=`key` exists in the same scope as the
             declaring eigenform (its parent container).
          2. If `expects` is set, that sibling is an instance of `cls`.

        Raises SiblingRefError on the first unresolved reference. The error
        message names the declaring eigenform, the scope, the missing key,
        and the sibling keys that do exist — actionable diagnostics for the
        usual cause (sibling renamed or deleted without updating dependents).

        Call site: PageForm.bind(), after children are bound. This closes
        the silent-orphan bug where a renamed sibling would leave its
        dependents quietly broken.
        """
        from engine.sibling_ref import SiblingRef, SiblingRefError

        # Build scope -> {key: eigenform} map by walking the bound tree.
        # Only include eigenforms with a scope (bound ones).
        scope_map: dict[str, dict[str, "Eigenform"]] = {}

        def _walk(ef):
            scope = getattr(ef, "_scope", None)
            if scope is not None:
                scope_map.setdefault(scope, {})[ef.key] = ef
            for child in ef.children:
                _walk(child)

        _walk(self)

        # Now walk again and validate each eigenform's sibling refs.
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

    def _reconstruct(self, stored_structure: list[dict]) -> list[Eigenform]:
        """Reconstruct eigenform list from stored descriptors + seed."""
        from engine.registry import from_descriptor, get_registry

        seed_by_key = {ef.key: ef for ef in self._seed}
        reg = get_registry()
        return [
            from_descriptor(desc, reg, seed=seed_by_key.get(desc.get("key")))
            for desc in stored_structure
        ]

    def _rebuild(self):
        """Reconstruct the live eigenform tree from __structure.

        Called after structural mutations (add/remove/move) to refresh
        the bound eigenform list from the updated stored structure.
        """
        stored = self._store.get(self.key, "__structure")
        if stored is None:
            return
        try:
            source = self._reconstruct(stored)
        except Exception:
            self._store.delete(self.key, "__structure")
            source = self._seed
        self.eigenforms = [
            ef.bind(store=self._store, scope=self.key, url_prefix=self._url_prefix)
            for ef in source
        ]

    def _rebuild_from_seed(self) -> dict:
        """Discard all structural changes and restore the original seed definition.

        Clears all stored data (values and structure), rewrites __structure
        from the seed, and rebinds from the seed eigenforms.
        """
        # Clear everything
        self._store.clear_scope(self._scope)
        self._store.clear_scope(self.key)
        self._clear_recursive(self.eigenforms)

        # Rewrite structure from seed
        structure = [ef.to_descriptor() for ef in self._seed]
        if self.mutable_structure:
            for desc in structure:
                desc["editable"] = True
        self._store.set(self.key, "__structure", structure)

        # Rebind from seed
        self.eigenforms = [
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
        elif action == "add_eigenform":
            self._set_feedback("success", f"Added {body.get('label', body.get('type', '?'))} ({body.get('key', '?')}).")
        elif action == "remove_eigenform":
            self._set_feedback("success", f"Removed '{body.get('key', '?')}'.")
        elif action == "move_eigenform":
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
        return all(ef.is_complete for ef in self.eigenforms)

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
            from engine.affordances import AddEigenformAffordance

            # Build structured catalog for agent JSON
            catalog = get_type_catalog()
            catalog_dict = {}
            for cat in catalog:
                heading = f"{cat['name']} \u2014 {cat['hint']}"
                catalog_dict[heading] = {
                    t: desc for t, _icon, desc in cat["types"]
                }

            affs.append(AddEigenformAffordance(
                label="Add Eigenform",
                method="POST",
                url=self._url_prefix,
                body={
                    "action": "add_eigenform",
                    "type": "<type>",
                    "key": "<optional - auto-generated from type if omitted>",
                    "label": "<optional - auto-generated from type if omitted>",
                },
                instruction=(
                    "Add a new eigenform to this page. Only 'type' is required "
                    "— key and label are auto-generated if omitted. After adding, "
                    "use edit mode to configure type-specific settings."
                ),
                type_catalog=catalog_dict,
            ))

            keys = [ef.key for ef in self.eigenforms]
            if keys:
                affs.append(SetValueAffordance(
                    label="Remove Eigenform",
                    method="POST",
                    url=self._url_prefix,
                    body={"action": "remove_eigenform", "key": "<key>"},
                    instruction=(
                        f"Remove an eigenform and its data. "
                        f"Valid keys: {', '.join(keys)}."
                    ),
                ))

            if len(keys) > 1:
                affs.append(SetValueAffordance(
                    label="Move Eigenform",
                    method="POST",
                    url=self._url_prefix,
                    body={
                        "action": "move_eigenform",
                        "key": "<key>",
                        "position": "<index>",
                    },
                    instruction=(
                        f"Move an eigenform to a new position (0-based index). "
                        f"Current order: {', '.join(keys)}."
                    ),
                ))

            if len(keys) >= 2:
                affs.append(SetValueAffordance(
                    label="Group Eigenforms",
                    method="POST",
                    url=self._url_prefix,
                    body={
                        "action": "group_eigenforms",
                        "keys": ["<key1>", "<key2>"],
                        "group_key": "<group_key>",
                        "group_label": "<group_label>",
                    },
                    instruction=(
                        f"Wrap two or more eigenforms in a new GroupForm. "
                        f"The group replaces them at the first selected position. "
                        f"Available keys: {', '.join(keys)}."
                    ),
                ))

            if keys:
                editable_keys = [ef.key for ef in self.eigenforms if ef.editable]
                locked_keys = [ef.key for ef in self.eigenforms if not ef.editable]
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
                        f"Toggle whether an eigenform is editable. "
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
        child_dicts = [s for ef in self.eigenforms
                       if (s := ef._serialize_full()) is not None]
        self._float_affordances(child_dicts, page_affs)
        # Strip render noise from children (what serialize() normally does)
        for d in child_dicts:
            d.pop("form", None)
            d.pop("key", None)
            for aff in d.get("affordances", []):
                aff.pop("render_hints", None)
                aff.pop("_chrome_rendered", None)
        state["eigenforms"] = child_dicts
        state["complete"] = self.is_complete
        state["affordances"] = page_affs
        return state

    def _float_affordances(self, child_dicts: list[dict],
                           page_affs: list[dict]) -> None:
        """Collect floatable affordances from the full eigenform tree."""
        merge_groups: dict[str, dict] = {}
        self._collect_floatable(child_dicts, merge_groups)

        _MERGED_INSTRUCTIONS = {
            "clear": "Clear all data from the target eigenform.",
            "edit": "Switch the target eigenform to edit mode.",
            "batch": (
                "Execute multiple actions on the target eigenform. "
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
        """Recursively walk eigenform dicts, extracting floatable affordances."""
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
            # Recurse into nested eigenforms
            if isinstance(ef_dict.get("eigenform"), dict):
                self._collect_floatable([ef_dict["eigenform"]], merge_groups)
            if isinstance(ef_dict.get("eigenforms"), list):
                self._collect_floatable(ef_dict["eigenforms"], merge_groups)
            if isinstance(ef_dict.get("sections"), dict):
                nested = [s["eigenform"] for s in ef_dict["sections"].values()
                          if isinstance(s, dict) and isinstance(s.get("eigenform"), dict)]
                self._collect_floatable(nested, merge_groups)

    def render_from_data(self, data: dict) -> str:
        from engine.registry import get_type_catalog
        children_html = [ef.render_safely() for ef in self.eigenforms]
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
                from engine.eigenform import Eigenform as EF
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

            for i, ef in enumerate(self.eigenforms):
                child_items.append({"key": ef.key, "index": i, "html": ef.render_safely(), "editable": ef.editable})
                tile_items.append(_build_tile(ef, i))
        return render_template("page.html", data=data, ef=self, url=self._url_prefix, label=data.get("label", ""), instruction=data.get("instruction") or "", children_html=children_html, child_items=child_items, tile_items=tile_items, type_catalog=type_catalog, feedback=data.get("feedback"), mutable=self.mutable_structure)

    def find_eigenform(self, path: str) -> Eigenform | None:
        """Find an eigenform by its path (e.g., 'tabs/title')."""
        segments = path.split("/")
        children = self.eigenforms
        for segment in segments:
            match = next((ef for ef in children if ef.key == segment), None)
            if match is None:
                return None
            if segment == segments[-1]:
                return match
            children = match.children
        return None

    def _clear_recursive(self, eigenforms: list[Eigenform]):
        """Clear state for all eigenforms, recursing via children property."""
        for ef in eigenforms:
            if ef._scope:
                self._store.clear_scope(ef._scope)
            self._clear_recursive(ef.children)

    # --- Structural mutation helpers ---

    def _get_structure(self) -> list[dict]:
        return list(self._store.get(self.key, "__structure") or [])

    def _save_structure(self, structure: list[dict]):
        self._store.set(self.key, "__structure", structure)

    def _handle(self, body: dict) -> dict:
        """Handle page-level actions."""
        action = body.get("action", "")

        if action == "dismiss_feedback":
            target = body.get("target", "")
            self._dismiss_feedback(target)
            return self.serialize()

        if action == "reset":
            if self.mutable_structure:
                # Mutable pages: clear everything including structure
                self._store.clear_scope(self._scope)
                self._store.clear_scope(self.key)
                self._clear_recursive(self.eigenforms)
                self._rebuild()
            else:
                # Fixed pages: preserve structure, clear data only
                structure = self._store.get(self.key, "__structure")
                self._store.clear_scope(self._scope)
                self._store.clear_scope(self.key)
                self._clear_recursive(self.eigenforms)
                if structure is not None:
                    self._store.set(self.key, "__structure", structure)
            return self.serialize()

        if not self.mutable_structure and action in (
            "add_eigenform", "remove_eigenform", "move_eigenform",
            "toggle_editable", "rebuild_from_seed", "group_eigenforms",
            "reparent_eigenform", "ungroup_eigenform",
        ):
            return self._error("Structural mutations not enabled on this page.", action=action)

        if action == "rebuild_from_seed":
            return self._rebuild_from_seed()
        elif action == "add_eigenform":
            return self._add_eigenform(body)
        elif action == "remove_eigenform":
            return self._remove_eigenform(body)
        elif action == "move_eigenform":
            return self._move_eigenform(body)
        elif action == "toggle_editable":
            return self._toggle_editable(body)
        elif action == "group_eigenforms":
            return self._group_eigenforms(body)
        elif action == "reparent_eigenform":
            return self._reparent_eigenform(body)
        elif action == "ungroup_eigenform":
            return self._ungroup_eigenform(body)

        return self.serialize()

    def _add_eigenform(self, body: dict) -> dict:
        from engine.registry import get_registry, validate_config

        type_name = body.get("type")
        config = body.get("config", {})
        after = body.get("after")

        if not type_name:
            return self._error("'type' is required.", action="add_eigenform")

        reg = get_registry()
        if type_name not in reg:
            return self._error(
                               f"Unknown type: {type_name}. Available: {', '.join(reg.available())}",
                               action="add_eigenform")

        # Collect all existing keys (at every depth) for uniqueness
        structure = self._get_structure()
        existing_keys = self._all_keys_in_tree(structure)

        # Auto-generate key if not provided
        key = body.get("key", "").strip()
        if not key:
            n = 1
            while f"{type_name}-{n}" in existing_keys:
                n += 1
            key = f"{type_name}-{n}"
        elif key in existing_keys:
            return self._error(f"Key '{key}' already exists.", action="add_eigenform")

        # Auto-generate label if not provided
        label = body.get("label", "").strip()
        if not label:
            label = type_name.replace("dynamicchoice", "dynamic choice").title()

        # Validate config before persisting
        if config:
            err = validate_config(type_name, config, reg)
            if err:
                return self._error(err, action="add_eigenform")

        # Build descriptor
        desc = {"type": type_name, "key": key, "label": label, "editable": True}
        if body.get("instruction"):
            desc["instruction"] = body["instruction"]
        if config:
            desc["config"] = config

        # Insert into structure (already fetched above for key uniqueness)
        position = body.get("position")
        if after:
            idx = next((i for i, d in enumerate(structure) if d["key"] == after), None)
            if idx is None:
                return self._error(f"Sibling '{after}' not found.", action="add_eigenform")
            structure.insert(idx + 1, desc)
        elif position is not None:
            pos = max(0, min(int(position), len(structure)))
            structure.insert(pos, desc)
        else:
            structure.append(desc)

        self._save_structure(structure)
        self._rebuild()
        # Expose generated key/label back to caller for feedback messages
        body.setdefault("key", key)
        body.setdefault("label", label)
        return self.serialize()

    def _clear_eigenform_data(self, ef: Eigenform):
        """Surgically clear stored data for one eigenform and its children.

        Unlike _clear_recursive (which uses clear_scope and can wipe siblings),
        this deletes only the eigenform's own key and any child sub-scopes
        that are distinct from the parent scope.
        """
        # Delete the eigenform's own stored value
        if ef._store and ef._scope:
            ef._store.delete(ef._scope, ef.key)
        # Clear child sub-scopes (containers store children in sub-scopes)
        for child in ef.children:
            if child._scope and child._scope != ef._scope:
                self._store.clear_scope(child._scope)
            self._clear_eigenform_data(child)

    def _find_eigenform_recursive(self, eigenforms: list, key: str):
        """Find a live eigenform by key at any depth."""
        for ef in eigenforms:
            if ef.key == key:
                return ef
            found = self._find_eigenform_recursive(ef.children, key)
            if found is not None:
                return found
        return None

    def _remove_eigenform(self, body: dict) -> dict:
        key = body.get("key")
        if not key:
            return self._error("'key' is required.", action="remove_eigenform")

        # Find the live eigenform to clear its data (search recursively)
        ef = self._find_eigenform_recursive(self.eigenforms, key)
        if ef is None:
            return self._error(f"Eigenform '{key}' not found.", action="remove_eigenform")

        # Surgically clear only this eigenform's data
        self._clear_eigenform_data(ef)

        structure = self._get_structure()

        # Find the parent container so we can sync its __structure after
        parent_key = self._find_parent_key(structure, key)

        # Remove from structure (recursive pluck)
        removed = self._pluck_from_tree(structure, key)
        if removed is None:
            return self._error(f"Eigenform '{key}' not found in structure.",
                               action="remove_eigenform")

        self._save_structure(structure)

        # Sync parent container's stored __structure
        if parent_key:
            self._sync_container_structure(structure, parent_key)

        self._rebuild()
        return self.serialize()

    def _move_eigenform(self, body: dict) -> dict:
        key = body.get("key")
        position = body.get("position")
        parent = body.get("parent")  # optional: reorder within a container

        if not key:
            return self._error("'key' is required.", action="move_eigenform")
        if position is None:
            return self._error("'position' is required.", action="move_eigenform")

        try:
            position = int(position)
        except (TypeError, ValueError):
            return self._error(f"Invalid position: {position}", action="move_eigenform")

        structure = self._get_structure()

        if parent:
            # Reorder within a container's children
            children = self._find_container_children(structure, parent)
            if children is None:
                return self._error(f"Container '{parent}' not found.",
                                   action="move_eigenform")
            idx = next((i for i, d in enumerate(children) if d["key"] == key), None)
            if idx is None:
                return self._error(f"Eigenform '{key}' not found in '{parent}'.",
                                   action="move_eigenform")
            desc = children.pop(idx)
            position = max(0, min(position, len(children)))
            children.insert(position, desc)
            self._save_structure(structure)
            self._sync_container_structure(structure, parent)
        else:
            # Move to top level — pluck from wherever it currently lives
            source_parent = self._find_parent_key(structure, key)
            desc = self._pluck_from_tree(structure, key)
            if desc is None:
                return self._error(f"Eigenform '{key}' not found.", action="move_eigenform")
            position = max(0, min(position, len(structure)))
            structure.insert(position, desc)
            self._save_structure(structure)
            if source_parent:
                self._sync_container_structure(structure, source_parent)

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

    @staticmethod
    def _find_siblings_list(tree: list[dict], key: str) -> list[dict] | None:
        """Find the children list that directly contains a descriptor with the given key."""
        for desc in tree:
            if desc["key"] == key:
                return tree
            for field in ("eigenforms", "steps"):
                children = desc.get(field)
                if isinstance(children, list):
                    result = PageForm._find_siblings_list(children, key)
                    if result is not None:
                        return result
        return None

    @staticmethod
    def _all_keys_in_tree(tree: list[dict]) -> set[str]:
        """Collect all keys at every depth in a structure tree."""
        keys = set()
        for desc in tree:
            keys.add(desc["key"])
            for field in ("eigenforms", "steps"):
                children = desc.get(field)
                if isinstance(children, list):
                    keys |= PageForm._all_keys_in_tree(children)
        return keys

    def _group_eigenforms(self, body: dict) -> dict:
        keys = body.get("keys", [])
        group_key = body.get("group_key")
        group_label = body.get("group_label", group_key)

        if not isinstance(keys, list) or len(keys) < 2:
            return self._error("Select at least 2 eigenforms to group.",
                               action="group_eigenforms")
        if not group_key:
            return self._error("'group_key' is required.",
                               action="group_eigenforms")

        structure = self._get_structure()

        # Check key uniqueness across the whole tree
        all_keys = self._all_keys_in_tree(structure)
        if group_key in all_keys:
            return self._error(f"Key '{group_key}' already exists.",
                               action="group_eigenforms")

        # Find the siblings list containing the first key
        siblings = self._find_siblings_list(structure, keys[0])
        if siblings is None:
            return self._error(f"Key '{keys[0]}' not found.",
                               action="group_eigenforms")

        # Verify all selected keys are in the same siblings list
        key_set = set(keys)
        sibling_keys = {d["key"] for d in siblings}
        missing = key_set - sibling_keys
        if missing:
            return self._error(
                f"All selected eigenforms must share the same parent. "
                f"Not found among siblings: {', '.join(sorted(missing))}",
                action="group_eigenforms")

        # Collect descriptors preserving order, track indices
        indices = []
        selected_descs = []
        for i, desc in enumerate(siblings):
            if desc["key"] in key_set:
                indices.append(i)
                selected_descs.append(desc)

        # Build GroupForm descriptor wrapping the selected eigenforms
        group_desc = {
            "type": "group",
            "key": group_key,
            "label": group_label,
            "editable": True,
            "eigenforms": selected_descs,
        }

        # Replace: insert group at first selected position, skip originals
        insert_pos = indices[0]
        index_set = set(indices)
        new_siblings = []
        for i, desc in enumerate(siblings):
            if i == insert_pos:
                new_siblings.append(group_desc)
            if i not in index_set:
                new_siblings.append(desc)

        # Mutate the list in place so the change propagates up
        siblings[:] = new_siblings

        self._save_structure(structure)

        # Sync the parent container's __structure if we're nested
        parent_key = self._find_parent_key(structure, group_key)
        if parent_key:
            self._sync_container_structure(structure, parent_key)

        self._rebuild()
        self._set_feedback("success", f"Grouped {len(keys)} eigenforms into '{group_key}'.")
        return self.serialize()

    # --- Recursive structure tree helpers ---

    @staticmethod
    def _pluck_from_tree(tree: list[dict], key: str) -> dict | None:
        """Remove and return a descriptor by key from a nested structure tree."""
        for i, desc in enumerate(tree):
            if desc["key"] == key:
                return tree.pop(i)
            # Recurse into container children
            children = desc.get("eigenforms") or desc.get("steps")
            if isinstance(children, list):
                found = PageForm._pluck_from_tree(children, key)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _find_container_children(tree: list[dict], key: str) -> list[dict] | None:
        """Find the children list of a container descriptor by key."""
        for desc in tree:
            if desc["key"] == key:
                # Return the eigenforms/steps list (create if needed)
                for field in ("eigenforms", "steps"):
                    if field in desc:
                        return desc[field]
                # Container types that use 'eigenforms'
                if desc.get("type") in ("group", "page"):
                    desc["eigenforms"] = desc.get("eigenforms", [])
                    return desc["eigenforms"]
                # NavigationForm uses 'steps'
                if desc.get("type") in ("navigation", "tab", "chain",
                                         "sequence", "accordion"):
                    desc["steps"] = desc.get("steps", [])
                    return desc["steps"]
                return None
            # Recurse
            for field in ("eigenforms", "steps"):
                children = desc.get(field)
                if isinstance(children, list):
                    result = PageForm._find_container_children(children, key)
                    if result is not None:
                        return result
        return None

    def _sync_container_structure(self, structure: list[dict], container_key: str):
        """Sync a container's own __structure in the store from the page tree.

        Editable containers (GroupForm, NavigationForm) store their own
        __structure.  After page-level mutations that modify their children,
        the container's stored structure must be updated to match.
        """
        children = self._find_container_children(structure, container_key)
        if children is not None:
            self._store.set(container_key, "__structure", list(children))

    @staticmethod
    def _find_parent_key(tree: list[dict], child_key: str) -> str | None:
        """Find the key of the container that holds a given child."""
        for desc in tree:
            for field in ("eigenforms", "steps"):
                children = desc.get(field)
                if isinstance(children, list):
                    for c in children:
                        if c.get("key") == child_key:
                            return desc["key"]
                    # Recurse deeper
                    result = PageForm._find_parent_key(children, child_key)
                    if result is not None:
                        return result
        return None

    def _ungroup_eigenform(self, body: dict) -> dict:
        key = body.get("key")
        if not key:
            return self._error("'key' is required.", action="ungroup_eigenform")

        structure = self._get_structure()

        # Find the siblings list containing this container
        siblings = self._find_siblings_list(structure, key)
        if siblings is None:
            return self._error(f"Eigenform '{key}' not found.",
                               action="ungroup_eigenform")

        # Find the descriptor
        idx = next((i for i, d in enumerate(siblings) if d["key"] == key), None)
        desc = siblings[idx]

        # Get its children
        children = desc.get("eigenforms") or desc.get("steps") or []
        if not children and desc.get("type") not in ("group", "navigation",
                                                      "page", "tab", "chain",
                                                      "sequence", "accordion"):
            return self._error(f"'{key}' is not a container.",
                               action="ungroup_eigenform")

        # Splice: replace the container with its children at the same position
        siblings[idx:idx + 1] = list(children)

        self._save_structure(structure)

        # Sync the grandparent container's __structure if nested
        grandparent = self._find_parent_key(structure, children[0]["key"]) if children else None
        if grandparent:
            self._sync_container_structure(structure, grandparent)

        # Clean up the ungrouped container's own stored scope
        self._store.clear_scope(key)

        self._rebuild()
        count = len(children)
        self._set_feedback("success",
                           f"Ungrouped '{key}': {count} eigenform{'s' if count != 1 else ''} "
                           f"moved to parent level.")
        return self.serialize()

    def _reparent_eigenform(self, body: dict) -> dict:
        key = body.get("key")
        target = body.get("target")  # container key, or null for top-level

        if not key:
            return self._error("'key' is required.", action="reparent_eigenform")

        structure = self._get_structure()

        # Find the source parent before plucking (for store sync)
        source_parent = self._find_parent_key(structure, key)

        # Pluck the descriptor from wherever it is
        desc = self._pluck_from_tree(structure, key)
        if desc is None:
            return self._error(f"Eigenform '{key}' not found.",
                               action="reparent_eigenform")

        if not target:
            # Move to top level (append at end)
            structure.append(desc)
        else:
            # Find the target container's children list
            children = self._find_container_children(structure, target)
            if children is None:
                # Put it back where it was (recovery) and error
                structure.append(desc)
                self._save_structure(structure)
                self._rebuild()
                return self._error(
                    f"Target '{target}' is not a container or not found.",
                    action="reparent_eigenform")
            children.append(desc)

        self._save_structure(structure)

        # Sync affected containers' own __structure in the store
        if source_parent:
            self._sync_container_structure(structure, source_parent)
        if target:
            self._sync_container_structure(structure, target)

        self._rebuild()
        target_label = target or "top level"
        self._set_feedback("success", f"Moved '{key}' into '{target_label}'.")
        return self.serialize()

    def handle_action(self, path: str, body: dict) -> dict | None:
        """Route a POST to the correct nested eigenform by path. Returns full page state."""
        ef = self.find_eigenform(path)
        if ef is None:
            return None
        result = ef.handle(body)

        # Phase E: apply structural actions returned by child eigenforms
        structural_actions = result.pop("_structural_actions", None)
        if structural_actions and self.mutable_structure:
            for sa in structural_actions:
                self._handle(sa)

        # Capture feedback
        if "error" in result:
            self._set_feedback("error", result["error"], target=path)
        else:
            action = body.get("action", "set")
            self._set_feedback("success", action, target=path)

        page_state = self.serialize()
        if "error" in result:
            page_state["error"] = result["error"]
            page_state["failed_action"] = result.get("failed_action")
        return page_state
