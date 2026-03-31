"""PageForm — an eigenform that contains and delegates to nested eigenforms."""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Any

from engine.affordances import (
    Affordance,
    SimpleButtonAffordance,
    SetValueAffordance,
    render_inline_button,
)
from engine.eigenform import Eigenform
from engine.store import Store


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
        from engine.affordances import render_affordance_html
        html = f'<h2>{escape(data["label"])}</h2>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        # Feedback banners
        fb = data.get("feedback")
        if fb:
            affs = data.get("affordances", [])

            # Index dismiss affordances by target for inline rendering
            dismiss_affs = {}
            for aff in affs:
                body = aff.get("body", {})
                if body.get("action") == "dismiss_feedback":
                    dismiss_affs[body.get("target", "")] = aff

            # Persistent errors (each with dismiss button from affordance)
            STYLE_DISMISS = (
                "cursor: pointer; font-size: 11px; padding: 1px 6px;"
                " background: transparent; border: 1px solid #c88; color: #721c24;"
                " border-radius: 3px;"
            )
            for err in fb.get("errors", []):
                target = err.get("target", "")
                target_label = f' <span style="opacity: 0.7;">({escape(target)})</span>' if target else ""
                dismiss_html = ""
                aff = dismiss_affs.get(target)
                if aff:
                    Eigenform.mark_rendered(aff)
                    dismiss_html = render_inline_button(
                        aff["url"], aff["body"], "&#10005;", STYLE_DISMISS,
                    )
                html += (
                    f'<div style="background: #fdecea; border: 1px solid #f5c6cb; color: #721c24;'
                    f' padding: 8px 12px; margin: 4px 0; border-radius: 4px;'
                    f' display: flex; justify-content: space-between; align-items: center;">'
                    f'<span><strong>&#10007; Error:</strong> {escape(err["message"])}{target_label}</span>'
                    f'<span style="display: flex; align-items: center; gap: 8px;">'
                    f'<span style="opacity: 0.5; font-size: 0.85em;">{escape(err.get("timestamp", ""))}</span>'
                    f'{dismiss_html}'
                    f'</span></div>'
                )
            # Latest success
            succ = fb.get("success")
            if succ:
                target = succ.get("target", "")
                target_label = f' <span style="opacity: 0.7;">({escape(target)})</span>' if target else ""
                html += (
                    f'<div style="background: #edf7ed; border: 1px solid #c3e6cb; color: #155724;'
                    f' padding: 8px 12px; margin: 4px 0; border-radius: 4px;'
                    f' display: flex; justify-content: space-between; align-items: center;">'
                    f'<span><strong>&#10003; OK:</strong> {escape(succ["message"])}{target_label}</span>'
                    f'<span style="opacity: 0.5; font-size: 0.85em;">{escape(succ.get("timestamp", ""))}</span>'
                    f'</div>'
                )
            if fb.get("errors") or succ:
                html += '<div style="margin-bottom: 8px;"></div>'

        if self.mutable_structure:
            html += self._render_mutable(data)
        else:
            html += "".join(ef.render() for ef in self.eigenforms)

        # Remaining non-structural affordances (Reset Page, etc.)
        html += '<div style="margin-top: 12px;">'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'
        return html

    def _render_mutable(self, data: dict) -> str:
        """Render a mutable page with an add toolbar and per-eigenform controls."""
        from engine.registry import get_registry
        affs = data.get("affordances", [])
        url = self._url_prefix

        # Mark all structural affordances as rendered (we handle them custom)
        remove_keys = {}
        move_keys = {}
        for aff in affs:
            body = aff.get("body", {})
            action = body.get("action", "")
            if action == "add_eigenform":
                Eigenform.mark_rendered(aff)
            elif action == "remove_eigenform":
                Eigenform.mark_rendered(aff)
                remove_keys[body.get("key")] = aff
            elif action == "move_eigenform":
                Eigenform.mark_rendered(aff)
                move_keys[body.get("key")] = aff
            elif action == "rebuild_from_seed":
                Eigenform.mark_rendered(aff)

        # --- Add Eigenform toolbar ---
        reg = get_registry()
        available = sorted(reg.available())
        type_options = "".join(
            f'<option value="{escape(t)}">{escape(t)}</option>' for t in available
        )
        html = (
            f'<div style="background: #f5f5f5; border: 1px solid #ddd; padding: 10px;'
            f' margin-bottom: 12px; border-radius: 4px;">'
            f'<form style="display: flex; gap: 8px; align-items: end; flex-wrap: wrap;" onsubmit="'
            f"var b={{action:'add_eigenform',type:this.elements.t.value,"
            f"key:this.elements.k.value,label:this.elements.l.value,config:{{}}}};"
            f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
            f'<div><label style="font-size: 11px; color: #666; display: block;">Type</label>'
            f'<select name="t" style="padding: 4px;">'
            f'<option value="">-- select type --</option>{type_options}</select></div>'
            f'<div><label style="font-size: 11px; color: #666; display: block;">Key</label>'
            f'<input name="k" type="text" placeholder="unique-key" style="padding: 4px; width: 140px;" /></div>'
            f'<div><label style="font-size: 11px; color: #666; display: block;">Label</label>'
            f'<input name="l" type="text" placeholder="Display Label" style="padding: 4px; width: 160px;" /></div>'
            f'<button type="submit" style="padding: 4px 14px; cursor: pointer;'
            f' background: #4a7; color: white; border: 1px solid #396; border-radius: 3px;">+ Add</button>'
            f'</form></div>'
        )

        # --- Eigenforms with inline controls ---
        n = len(self.eigenforms)
        for i, ef in enumerate(self.eigenforms):
            key = ef.key
            # Control bar
            ctrl = (
                f'<div style="display: flex; align-items: center; gap: 4px;'
                f' padding: 4px 8px; background: #fafafa; border: 1px solid #e0e0e0;'
                f' border-bottom: none; border-radius: 4px 4px 0 0; font-size: 11px; color: #666;">'
                f'<span style="font-family: monospace; background: #eee; padding: 1px 5px;'
                f' border-radius: 2px;">{escape(key)}</span>'
                f'<span style="flex: 1;"></span>'
            )
            # Move up
            if i > 0:
                ctrl += render_inline_button(
                    url, {"action": "move_eigenform", "key": key, "position": i - 1},
                    "&#9650;",
                    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
                    " width: 22px; height: 22px; font-size: 9px; padding: 0;"
                )
            else:
                ctrl += (
                    '<span style="display: inline-block; width: 22px; height: 22px;'
                    ' border: 1px solid transparent;"></span>'
                )
            # Move down
            if i < n - 1:
                ctrl += render_inline_button(
                    url, {"action": "move_eigenform", "key": key, "position": i + 1},
                    "&#9660;",
                    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
                    " width: 22px; height: 22px; font-size: 9px; padding: 0;"
                )
            else:
                ctrl += (
                    '<span style="display: inline-block; width: 22px; height: 22px;'
                    ' border: 1px solid transparent;"></span>'
                )
            # Remove
            ctrl += render_inline_button(
                url, {"action": "remove_eigenform", "key": key},
                "&#10005;",
                "cursor: pointer; border: 1px solid #dcc; background: #fef8f8;"
                " width: 22px; height: 22px; font-size: 10px; padding: 0; color: #c00;"
                " margin-left: 4px;"
            )
            ctrl += '</div>'

            # Eigenform content in bordered container
            html += (
                f'<div style="margin-bottom: 8px;">'
                f'{ctrl}'
                f'<div style="border: 1px solid #e0e0e0; border-radius: 0 0 4px 4px;'
                f' padding: 8px;">'
                f'{ef.render()}'
                f'</div></div>'
            )

        if not self.eigenforms:
            html += (
                '<div style="padding: 24px; text-align: center; color: #999;'
                ' border: 2px dashed #ddd; border-radius: 4px; margin-bottom: 8px;">'
                'No eigenforms yet. Use the toolbar above to add one.</div>'
            )

        # Rebuild from seed button (subtle, at the bottom)
        html += (
            f'<div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #eee;">'
        )
        html += render_inline_button(
            url, {"action": "rebuild_from_seed"},
            "&#8634; Rebuild from Seed",
            "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
            " font-size: 11px; padding: 3px 10px; color: #888;"
        )
        html += '</div>'

        return html

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
