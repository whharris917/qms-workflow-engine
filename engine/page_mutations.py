"""Page structural mutations — extracted from page.py.

Contains all methods that modify the page's component structure tree:
add, remove, move, toggle_editable, group, ungroup, reparent.
Also contains the recursive tree helpers and handle_action routing.

Mixed into Page via PageMutationsMixin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.component import Component


class PageMutationsMixin:
    """Structural mutation implementations for Page."""

    def _do_rebuild_from_seed(self, body: dict) -> dict:
        if not self.mutable_structure:
            return self._error("Structural mutations not enabled on this page.", action="rebuild_from_seed")
        return self._rebuild_from_seed()

    def _do_add_component(self, body: dict) -> dict:
        if not self.mutable_structure:
            return self._error("Structural mutations not enabled on this page.", action="add_component")
        return self._add_component(body)

    def _do_remove_component(self, body: dict) -> dict:
        if not self.mutable_structure:
            return self._error("Structural mutations not enabled on this page.", action="remove_component")
        return self._remove_component(body)

    def _do_move_component(self, body: dict) -> dict:
        if not self.mutable_structure:
            return self._error("Structural mutations not enabled on this page.", action="move_component")
        return self._move_component(body)

    def _do_toggle_editable(self, body: dict) -> dict:
        if not self.mutable_structure:
            return self._error("Structural mutations not enabled on this page.", action="toggle_editable")
        return self._toggle_editable(body)

    def _do_group_components(self, body: dict) -> dict:
        if not self.mutable_structure:
            return self._error("Structural mutations not enabled on this page.", action="group_components")
        return self._group_components(body)

    def _do_reparent_component(self, body: dict) -> dict:
        if not self.mutable_structure:
            return self._error("Structural mutations not enabled on this page.", action="reparent_component")
        return self._reparent_component(body)

    def _do_ungroup_component(self, body: dict) -> dict:
        if not self.mutable_structure:
            return self._error("Structural mutations not enabled on this page.", action="ungroup_component")
        return self._ungroup_component(body)

    # --- Structural mutation implementations ---

    def _add_component(self, body: dict) -> dict:
        from engine.registry import get_registry, validate_config

        type_name = body.get("type")
        config = body.get("config", {})
        after = body.get("after")

        if not type_name:
            return self._error("'type' is required.", action="add_component")

        reg = get_registry()
        if type_name not in reg:
            return self._error(
                               f"Unknown type: {type_name}. Available: {', '.join(reg.available())}",
                               action="add_component")

        structure = self._get_structure()
        existing_keys = self._all_keys_in_tree(structure)

        key = body.get("key", "").strip()
        if not key:
            n = 1
            while f"{type_name}-{n}" in existing_keys:
                n += 1
            key = f"{type_name}-{n}"
        elif key in existing_keys:
            return self._error(f"Key '{key}' already exists.", action="add_component")

        label = body.get("label", "").strip()
        if not label:
            label = type_name.title()

        if config:
            err = validate_config(type_name, config, reg)
            if err:
                return self._error(err, action="add_component")

        desc = {"type": type_name, "key": key, "label": label, "editable": True}
        if body.get("instruction"):
            desc["instruction"] = body["instruction"]
        if config:
            desc["config"] = config

        position = body.get("position")
        if after:
            idx = next((i for i, d in enumerate(structure) if d["key"] == after), None)
            if idx is None:
                return self._error(f"Sibling '{after}' not found.", action="add_component")
            structure.insert(idx + 1, desc)
        elif position is not None:
            pos = max(0, min(int(position), len(structure)))
            structure.insert(pos, desc)
        else:
            structure.append(desc)

        self._save_structure(structure)
        self._rebuild()
        body.setdefault("key", key)
        body.setdefault("label", label)
        return self.serialize()

    def _clear_component_data(self, ef: "Component"):
        """Surgically clear stored data for one component and its children."""
        if ef._store and ef._scope:
            ef._store.delete(ef._scope, ef.key)
        for child in ef.children:
            if child._scope and child._scope != ef._scope:
                self._store.clear_scope(child._scope)
            self._clear_component_data(child)

    def _find_component_recursive(self, components: list, key: str):
        """Find a live component by key at any depth."""
        for ef in components:
            if ef.key == key:
                return ef
            found = self._find_component_recursive(ef.children, key)
            if found is not None:
                return found
        return None

    def _remove_component(self, body: dict) -> dict:
        key = body.get("key")
        if not key:
            return self._error("'key' is required.", action="remove_component")

        ef = self._find_component_recursive(self.components, key)
        if ef is None:
            return self._error(f"Component '{key}' not found.", action="remove_component")

        self._clear_component_data(ef)

        structure = self._get_structure()
        parent_key = self._find_parent_key(structure, key)

        removed = self._pluck_from_tree(structure, key)
        if removed is None:
            return self._error(f"Component '{key}' not found in structure.",
                               action="remove_component")

        self._save_structure(structure)

        if parent_key:
            self._sync_container_structure(structure, parent_key)

        self._rebuild()
        return self.serialize()

    def _move_component(self, body: dict) -> dict:
        key = body.get("key")
        position = body.get("position")
        parent = body.get("parent")

        if not key:
            return self._error("'key' is required.", action="move_component")
        if position is None:
            return self._error("'position' is required.", action="move_component")

        try:
            position = int(position)
        except (TypeError, ValueError):
            return self._error(f"Invalid position: {position}", action="move_component")

        structure = self._get_structure()

        if parent:
            children = self._find_container_children(structure, parent)
            if children is None:
                return self._error(f"Container '{parent}' not found.",
                                   action="move_component")
            idx = next((i for i, d in enumerate(children) if d["key"] == key), None)
            if idx is None:
                return self._error(f"Component '{key}' not found in '{parent}'.",
                                   action="move_component")
            desc = children.pop(idx)
            position = max(0, min(position, len(children)))
            children.insert(position, desc)
            self._save_structure(structure)
            self._sync_container_structure(structure, parent)
        else:
            source_parent = self._find_parent_key(structure, key)
            desc = self._pluck_from_tree(structure, key)
            if desc is None:
                return self._error(f"Component '{key}' not found.", action="move_component")
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
            return self._error(f"Component '{key}' not found.",
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
            for field in ("components", "steps"):
                children = desc.get(field)
                if isinstance(children, list):
                    result = PageMutationsMixin._find_siblings_list(children, key)
                    if result is not None:
                        return result
        return None

    @staticmethod
    def _all_keys_in_tree(tree: list[dict]) -> set[str]:
        """Collect all keys at every depth in a structure tree."""
        keys = set()
        for desc in tree:
            keys.add(desc["key"])
            for field in ("components", "steps"):
                children = desc.get(field)
                if isinstance(children, list):
                    keys |= PageMutationsMixin._all_keys_in_tree(children)
        return keys

    def _group_components(self, body: dict) -> dict:
        keys = body.get("keys", [])
        group_key = body.get("group_key")
        group_label = body.get("group_label", group_key)

        if not isinstance(keys, list) or len(keys) < 2:
            return self._error("Select at least 2 components to group.",
                               action="group_components")
        if not group_key:
            return self._error("'group_key' is required.",
                               action="group_components")

        structure = self._get_structure()

        all_keys = self._all_keys_in_tree(structure)
        if group_key in all_keys:
            return self._error(f"Key '{group_key}' already exists.",
                               action="group_components")

        siblings = self._find_siblings_list(structure, keys[0])
        if siblings is None:
            return self._error(f"Key '{keys[0]}' not found.",
                               action="group_components")

        key_set = set(keys)
        sibling_keys = {d["key"] for d in siblings}
        missing = key_set - sibling_keys
        if missing:
            return self._error(
                f"All selected components must share the same parent. "
                f"Not found among siblings: {', '.join(sorted(missing))}",
                action="group_components")

        indices = []
        selected_descs = []
        for i, desc in enumerate(siblings):
            if desc["key"] in key_set:
                indices.append(i)
                selected_descs.append(desc)

        group_desc = {
            "type": "group",
            "key": group_key,
            "label": group_label,
            "editable": True,
            "components": selected_descs,
        }

        insert_pos = indices[0]
        index_set = set(indices)
        new_siblings = []
        for i, desc in enumerate(siblings):
            if i == insert_pos:
                new_siblings.append(group_desc)
            if i not in index_set:
                new_siblings.append(desc)

        siblings[:] = new_siblings

        self._save_structure(structure)

        parent_key = self._find_parent_key(structure, group_key)
        if parent_key:
            self._sync_container_structure(structure, parent_key)

        self._rebuild()
        self._set_feedback("success", f"Grouped {len(keys)} components into '{group_key}'.")
        return self.serialize()

    # --- Recursive structure tree helpers ---

    @staticmethod
    def _pluck_from_tree(tree: list[dict], key: str) -> dict | None:
        """Remove and return a descriptor by key from a nested structure tree."""
        for i, desc in enumerate(tree):
            if desc["key"] == key:
                return tree.pop(i)
            children = desc.get("components") or desc.get("steps")
            if isinstance(children, list):
                found = PageMutationsMixin._pluck_from_tree(children, key)
                if found is not None:
                    return found
        return None

    @staticmethod
    def _find_container_children(tree: list[dict], key: str) -> list[dict] | None:
        """Find the children list of a container descriptor by key."""
        for desc in tree:
            if desc["key"] == key:
                for field in ("components", "steps"):
                    if field in desc:
                        return desc[field]
                if desc.get("type") in ("group", "page"):
                    desc["components"] = desc.get("components", [])
                    return desc["components"]
                if desc.get("type") in ("navigation", "tab", "chain",
                                         "sequence", "accordion"):
                    desc["steps"] = desc.get("steps", [])
                    return desc["steps"]
                return None
            for field in ("components", "steps"):
                children = desc.get(field)
                if isinstance(children, list):
                    result = PageMutationsMixin._find_container_children(children, key)
                    if result is not None:
                        return result
        return None

    def _sync_container_structure(self, structure: list[dict], container_key: str):
        """Sync a container's own __structure in the store from the page tree."""
        children = self._find_container_children(structure, container_key)
        if children is not None:
            self._store.set(container_key, "__structure", list(children))

    @staticmethod
    def _find_parent_key(tree: list[dict], child_key: str) -> str | None:
        """Find the key of the container that holds a given child."""
        for desc in tree:
            for field in ("components", "steps"):
                children = desc.get(field)
                if isinstance(children, list):
                    for c in children:
                        if c.get("key") == child_key:
                            return desc["key"]
                    result = PageMutationsMixin._find_parent_key(children, child_key)
                    if result is not None:
                        return result
        return None

    def _ungroup_component(self, body: dict) -> dict:
        key = body.get("key")
        if not key:
            return self._error("'key' is required.", action="ungroup_component")

        structure = self._get_structure()

        siblings = self._find_siblings_list(structure, key)
        if siblings is None:
            return self._error(f"Component '{key}' not found.",
                               action="ungroup_component")

        idx = next((i for i, d in enumerate(siblings) if d["key"] == key), None)
        desc = siblings[idx]

        children = desc.get("components") or desc.get("steps") or []
        if not children and desc.get("type") not in ("group", "navigation",
                                                      "page", "tab", "chain",
                                                      "sequence", "accordion"):
            return self._error(f"'{key}' is not a container.",
                               action="ungroup_component")

        siblings[idx:idx + 1] = list(children)

        self._save_structure(structure)

        grandparent = self._find_parent_key(structure, children[0]["key"]) if children else None
        if grandparent:
            self._sync_container_structure(structure, grandparent)

        self._store.clear_scope(key)

        self._rebuild()
        count = len(children)
        self._set_feedback("success",
                           f"Ungrouped '{key}': {count} component{'s' if count != 1 else ''} "
                           f"moved to parent level.")
        return self.serialize()

    def _reparent_component(self, body: dict) -> dict:
        key = body.get("key")
        target = body.get("target")

        if not key:
            return self._error("'key' is required.", action="reparent_component")

        structure = self._get_structure()

        source_parent = self._find_parent_key(structure, key)

        desc = self._pluck_from_tree(structure, key)
        if desc is None:
            return self._error(f"Component '{key}' not found.",
                               action="reparent_component")

        if not target:
            structure.append(desc)
        else:
            children = self._find_container_children(structure, target)
            if children is None:
                structure.append(desc)
                self._save_structure(structure)
                self._rebuild()
                return self._error(
                    f"Target '{target}' is not a container or not found.",
                    action="reparent_component")
            children.append(desc)

        self._save_structure(structure)

        if source_parent:
            self._sync_container_structure(structure, source_parent)
        if target:
            self._sync_container_structure(structure, target)

        self._rebuild()
        target_label = target or "top level"
        self._set_feedback("success", f"Moved '{key}' into '{target_label}'.")
        return self.serialize()

    def handle_action(self, path: str, body: dict) -> dict | None:
        """Route a POST to the correct nested component by path. Returns full page state."""
        ef = self.find_component(path)
        if ef is None:
            return None
        result = ef.handle(body)

        structural_actions = result.pop("_structural_actions", None)
        if structural_actions and self.mutable_structure:
            for sa in structural_actions:
                self.handle(sa)

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
