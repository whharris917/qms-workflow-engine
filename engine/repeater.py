"""RepeaterForm — a container that stamps out a template of eigenforms per entry.

Each entry is a group of eigenforms instantiated from a template. Entries
have stable IDs (entry_0, entry_1, ...) and each entry's eigenform data
lives in its own scope (e.g., "repeater_key/entry_0"), preventing collisions.

An inner EntryGroup class provides routing — find_eigenform can walk
repeater_key -> entry_0 -> field_name naturally via the children property.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.eigenforms import Eigenform
from engine.store import Store


@dataclass
class EntryGroup(Eigenform):
    """A lightweight container representing one entry in a RepeaterForm.

    Not constructed directly — created by RepeaterForm._bind_children().
    Its children are the stamped-and-bound template eigenforms for this entry.
    """
    eigenforms: list[Eigenform] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return False  # Internal container; parent RepeaterForm handles clearing

    @property
    def children(self) -> list[Eigenform]:
        return self.eigenforms

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.eigenforms)

    def _serialize_state(self) -> dict:
        return {
            "form": "entry",
            "key": self.key,
            "label": self.label,
            "eigenforms": [s for ef in self.eigenforms if (s := ef.serialize()) is not None],
        }

    def render_from_data(self, data: dict) -> str:
        html = f'<h4 style="margin: 4px 0;">{escape(data["label"])}</h4>'
        html += "".join(ef.render() for ef in self.eigenforms)
        return html

    def get_affordances(self) -> list[Affordance]:
        return []

    def _handle(self, body: dict) -> dict:
        return self.serialize()


@dataclass
class RepeaterForm(Eigenform):
    """A container that stamps out a template of eigenforms per dynamic entry.

    Usage:
        RepeaterForm(key="employees", label="Employees", template=[
            TextForm(key="name", label="Name"),
            ChoiceForm(key="role", label="Role", options=["Dev", "QA", "PM"]),
            DateForm(key="start_date", label="Start Date"),
        ], min_entries=1)
    """
    template: list[Eigenform] = field(default_factory=list)
    min_entries: int = 0
    max_entries: int | None = None
    entry_label: str = "Entry"

    # Populated at bind time
    _entry_groups: list[EntryGroup] = field(default_factory=list, repr=False)

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["template"] = [ef.to_descriptor() for ef in self.template]
        return desc

    @property
    def has_data(self) -> bool:
        return len(self._entry_ids) > 0

    def _clear_data(self):
        """Clear all entries and their sub-scoped data."""
        for entry_id in self._entry_ids:
            self._store.clear_scope(f"{self.key}/{entry_id}")
        self._store.delete(self._scope, self.key)
        self._rebuild_entries()

    @property
    def _structural_state(self) -> dict:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored
        return {"entries": [], "next_id": 0}

    @property
    def _entry_ids(self) -> list[str]:
        return self._structural_state.get("entries", [])

    @property
    def _next_id(self) -> int:
        return self._structural_state.get("next_id", 0)

    @property
    def children(self) -> list[Eigenform]:
        return list(self._entry_groups)

    @property
    def is_complete(self) -> bool:
        entry_count = len(self._entry_ids)
        if entry_count < self.min_entries:
            return False
        return all(eg.is_complete for eg in self._entry_groups)

    def _bind_children(self, store: Store, url_prefix: str):
        """Instantiate EntryGroups for all existing entries."""
        self._entry_groups = []
        for idx, entry_id in enumerate(self._entry_ids):
            entry_scope = f"{self.key}/{entry_id}"
            entry_url = f"{url_prefix}/{self.key}"
            stamped = [
                ef.bind(store=store, scope=entry_scope, url_prefix=f"{entry_url}/{entry_id}")
                for ef in copy.deepcopy(self.template)
            ]
            group = EntryGroup(
                key=entry_id,
                label=f"{self.entry_label} {idx + 1}",
                eigenforms=stamped,
            )
            group._store = store
            group._scope = entry_scope
            group._url_prefix = f"{entry_url}"
            self._entry_groups.append(group)

    def _rebuild_entries(self):
        """Re-instantiate entry groups after structural change."""
        if self._store is not None:
            self._bind_children(self._store, self._url_prefix)

    def _save_structural(self, entries: list[str], next_id: int):
        self._store.set(self._scope, self.key, {
            "entries": entries,
            "next_id": next_id,
        })

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "entry_count": len(self._entry_ids),
            "min_entries": self.min_entries,
            "max_entries": self.max_entries,
            "entries": [eg.serialize() for eg in self._entry_groups],
        }

    def get_affordances(self) -> list[Affordance]:
        affs: list[Affordance] = []

        at_max = self.max_entries is not None and len(self._entry_ids) >= self.max_entries
        if not at_max:
            affs.append(SimpleButtonAffordance(
                label=f"+ Add {self.entry_label}",
                method="POST",
                url=self.url,
                body={"action": "add"},
                instruction=f"Add a new {self.entry_label.lower()}.",
            ))

        for entry_id in self._entry_ids:
            affs.append(SimpleButtonAffordance(
                label=f"Remove {entry_id}",
                method="POST",
                url=self.url,
                body={"action": "remove", "id": entry_id},
                instruction=f"Remove {entry_id} and all its data.",
            ))

        return affs

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        html += f'<p><strong>{data["entry_count"]}</strong> {escape(self.entry_label.lower())}(s)'
        if self.min_entries > 0:
            html += f' (min: {self.min_entries})'
        if self.max_entries is not None:
            html += f' (max: {self.max_entries})'
        html += '</p>'

        # Render each entry group with its remove button
        affs = data.get("affordances", [])
        remove_affs = {}
        for aff in affs:
            if aff.get("body", {}).get("action") == "remove":
                remove_affs[aff["body"]["id"]] = aff
                Eigenform.mark_rendered(aff)

        for idx, eg in enumerate(self._entry_groups):
            entry_id = eg.key
            html += (
                f'<div style="border: 1px solid #ddd; padding: 8px; margin: 8px 0;'
                f' border-radius: 4px; position: relative;">'
                f'<div style="display: flex; justify-content: space-between; align-items: center;">'
                f'<strong>{escape(self.entry_label)} {idx + 1}</strong>'
            )
            # Inline remove button
            if entry_id in remove_affs:
                body_js = json.dumps(remove_affs[entry_id]["body"]).replace('"', '&quot;')
                html += (
                    f'<button onclick="fetch(\'{self.url}\','
                    f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                    f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
                    f' style="cursor: pointer; font-size: 11px; padding: 2px 8px;'
                    f' color: #c00; border: 1px solid #ccc; background: #f8f8f8;"'
                    f' title="Remove {escape(entry_id)}">Remove</button>'
                )
            html += '</div>'
            html += "".join(ef.render() for ef in eg.eigenforms)
            html += '</div>'

        # Remaining affordances (add button)
        html += '<div style="margin-top: 8px;">'
        for aff in affs:
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'

        return html

    def _error(self, action: str, msg: str) -> dict:
        result = self.serialize()
        result["error"] = msg
        result["failed_action"] = action
        return result

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")
        entries = list(self._entry_ids)
        next_id = self._next_id

        if action == "add":
            if self.max_entries is not None and len(entries) >= self.max_entries:
                return self._error(action, f"Maximum {self.max_entries} entries reached.")
            entry_id = f"entry_{next_id}"
            entries.append(entry_id)
            next_id += 1
            self._save_structural(entries, next_id)
            self._rebuild_entries()

        elif action == "remove":
            entry_id = body.get("id", "")
            if entry_id not in entries:
                return self._error(action, f"Unknown entry: {entry_id}.")
            # Clear the entry's scope
            entry_scope = f"{self.key}/{entry_id}"
            self._store.clear_scope(entry_scope)
            entries.remove(entry_id)
            self._save_structural(entries, next_id)
            self._rebuild_entries()

        else:
            return self._error(action, f"Unknown action: {action}")

        return self.serialize()
