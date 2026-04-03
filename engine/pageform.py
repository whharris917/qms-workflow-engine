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

    def bind(self, data_dir: Path, scope: str, url_prefix: str) -> PageForm:
        """Produce a bound copy of this page and all nested eigenforms.

        Unlike other eigenforms, PageForm creates its own Store from
        data_dir rather than receiving one. This makes the page the
        persistence boundary — one JSON file per page.

        Structural persistence (Phase C): on first bind, the eigenform
        tree is serialized to __structure in the store. On subsequent
        binds, the stored structure is read and used to reconstruct the
        tree — matching seed eigenforms by key to preserve callables.
        If the stored structure is missing or corrupt, falls back to
        the Python seed definition.
        """
        import copy
        from engine.registry import from_descriptor, get_registry

        store = Store(data_dir / f"{scope}.json")
        bound = copy.deepcopy(self)
        bound._store = store
        bound._scope = scope
        bound._url_prefix = url_prefix

        # Preserve unbound seed for _rebuild() callable matching
        bound._seed = list(bound.eigenforms)

        # --- Structural persistence ---
        stored_structure = store.get(scope, "__structure")

        if stored_structure is None:
            # First bind: write seed structure to store
            structure = [ef.to_descriptor() for ef in bound._seed]
            store.set(scope, "__structure", structure)
            source = bound._seed
        else:
            # Subsequent bind: reconstruct from stored structure
            source = bound._reconstruct(stored_structure)

        bound.eigenforms = [
            ef.bind(store=store, scope=bound.key, url_prefix=url_prefix)
            for ef in source
        ]

        return bound

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
        stored = self._store.get(self._scope, "__structure")
        if stored is None:
            return
        source = self._reconstruct(stored)
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
        self._clear_recursive(self.eigenforms)

        # Rewrite structure from seed
        structure = [ef.to_descriptor() for ef in self._seed]
        self._store.set(self._scope, "__structure", structure)

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
            self._set_feedback("success", f"Added '{body.get('key', '?')}'.")
        elif action == "remove_eigenform":
            self._set_feedback("success", f"Removed '{body.get('key', '?')}'.")
        elif action == "move_eigenform":
            self._set_feedback("success",
                               f"Moved '{body.get('key', '?')}' to position {body.get('position', '?')}.")
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
            from engine.registry import get_registry
            reg = get_registry()
            available = reg.available()

            affs.append(SetValueAffordance(
                label="Add Eigenform",
                method="POST",
                url=self._url_prefix,
                body={
                    "action": "add_eigenform",
                    "type": "<type>",
                    "key": "<unique_key>",
                    "label": "<label>",
                    "config": {},
                    "after": "<sibling_key | null>",
                },
                instruction=(
                    f"Add a new eigenform to this page. "
                    f"Available types: {', '.join(available)}. "
                    f"'after' places it after the named sibling (null = append to end). "
                    f"'config' is type-specific (e.g. {{\"options\": [\"A\", \"B\"]}} for choice)."
                ),
            ))

            for ef in self.eigenforms:
                affs.append(SimpleButtonAffordance(
                    label=f"Remove {ef.key}",
                    method="POST",
                    url=self._url_prefix,
                    body={"action": "remove_eigenform", "key": ef.key},
                    instruction=f"Remove the '{ef.key}' eigenform and its data.",
                ))

            affs.append(SimpleButtonAffordance(
                label="Rebuild from Seed",
                method="POST",
                url=self._url_prefix,
                body={"action": "rebuild_from_seed"},
                instruction="Discard all structural changes and restore the original page definition. Clears all data.",
            ))

            if len(self.eigenforms) > 1:
                for ef in self.eigenforms:
                    affs.append(SetValueAffordance(
                        label=f"Move {ef.key}",
                        method="POST",
                        url=self._url_prefix,
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
        state["eigenforms"] = [s for ef in self.eigenforms if (s := ef.serialize()) is not None]
        state["complete"] = self.is_complete
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def render_from_data(self, data: dict) -> str:
        from engine.registry import get_registry
        children_html = [ef.render() for ef in self.eigenforms]
        child_items = []
        available_types = []
        if self.mutable_structure:
            available_types = sorted(get_registry().available())
            for i, ef in enumerate(self.eigenforms):
                child_items.append({"key": ef.key, "index": i, "html": ef.render()})
        return render_template("page.html", data=data, ef=self, url=self._url_prefix, label=data.get("label", ""), instruction=data.get("instruction") or "", children_html=children_html, child_items=child_items, available_types=available_types, feedback=data.get("feedback"), mutable=self.mutable_structure)

    def render_agent(self) -> str:
        """Render page for agent consumption — children use agent rendering."""
        data = self._serialize_full()
        children_html = [ef.render_agent() for ef in self.eigenforms]
        return render_template("page.html", data=data, ef=self, url=self._url_prefix, label=data.get("label", ""), instruction=data.get("instruction") or "", children_html=children_html, child_items=[], available_types=[], feedback=data.get("feedback"), mutable=False)

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
        return list(self._store.get(self._scope, "__structure") or [])

    def _save_structure(self, structure: list[dict]):
        self._store.set(self._scope, "__structure", structure)

    def _handle(self, body: dict) -> dict:
        """Handle page-level actions."""
        action = body.get("action", "")

        if action == "dismiss_feedback":
            target = body.get("target", "")
            self._dismiss_feedback(target)
            return self.serialize()

        if action == "reset":
            structure = self._store.get(self._scope, "__structure")
            self._store.clear_scope(self._scope)
            self._clear_recursive(self.eigenforms)
            if structure is not None:
                self._store.set(self._scope, "__structure", structure)
            return self.serialize()

        if not self.mutable_structure and action in (
            "add_eigenform", "remove_eigenform", "move_eigenform", "rebuild_from_seed",
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

        return self.serialize()

    def _add_eigenform(self, body: dict) -> dict:
        from engine.registry import get_registry

        type_name = body.get("type")
        key = body.get("key")
        label = body.get("label", key)
        config = body.get("config", {})
        after = body.get("after")

        if not type_name or not key:
            return self._error("Both 'type' and 'key' are required.", action="add_eigenform")

        reg = get_registry()
        if type_name not in reg:
            return self._error(
                               f"Unknown type: {type_name}. Available: {', '.join(reg.available())}",
                               action="add_eigenform")

        existing_keys = {ef.key for ef in self.eigenforms}
        if key in existing_keys:
            return self._error(f"Key '{key}' already exists.", action="add_eigenform")

        # Build descriptor
        desc = {"type": type_name, "key": key, "label": label, "editable": True}
        if body.get("instruction"):
            desc["instruction"] = body["instruction"]
        if config:
            desc["config"] = config

        # Insert into structure
        structure = self._get_structure()
        if after:
            idx = next((i for i, d in enumerate(structure) if d["key"] == after), None)
            if idx is None:
                return self._error(f"Sibling '{after}' not found.", action="add_eigenform")
            structure.insert(idx + 1, desc)
        else:
            structure.append(desc)

        self._save_structure(structure)
        self._rebuild()
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

    def _remove_eigenform(self, body: dict) -> dict:
        key = body.get("key")
        if not key:
            return self._error("'key' is required.", action="remove_eigenform")

        # Find the live eigenform to clear its data
        ef = next((e for e in self.eigenforms if e.key == key), None)
        if ef is None:
            return self._error(f"Eigenform '{key}' not found.", action="remove_eigenform")

        # Surgically clear only this eigenform's data
        self._clear_eigenform_data(ef)

        # Remove from structure
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
            return self._error("'position' is required.", action="move_eigenform")

        try:
            position = int(position)
        except (TypeError, ValueError):
            return self._error(f"Invalid position: {position}", action="move_eigenform")

        structure = self._get_structure()
        idx = next((i for i, d in enumerate(structure) if d["key"] == key), None)
        if idx is None:
            return self._error(f"Eigenform '{key}' not found.", action="move_eigenform")

        # Remove and reinsert at new position
        desc = structure.pop(idx)
        position = max(0, min(position, len(structure)))
        structure.insert(position, desc)

        self._save_structure(structure)
        self._rebuild()
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
            self._set_feedback("success", f"{action} \u2192 {path}", target=path)

        page_state = self.serialize()
        if "error" in result:
            page_state["error"] = result["error"]
            page_state["failed_action"] = result.get("failed_action")
        return page_state
