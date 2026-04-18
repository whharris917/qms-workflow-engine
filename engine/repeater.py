"""Repeater — a container that stamps out a template of components per entry.

Each entry is a group of components instantiated from a template. Entries
have stable IDs (entry_0, entry_1, ...) and each entry's component data
lives in its own scope (e.g., "repeater_key/entry_0"), preventing collisions.

An inner EntryGroup class provides routing — find_component can walk
repeater_key -> entry_0 -> field_name naturally via the children property.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.component import Component
from engine.templates import render_template
from engine.store import Store


@dataclass
class EntryGroup(Component):
    """A lightweight container representing one entry in a Repeater.

    Not constructed directly — created by Repeater._bind_children().
    Its children are the stamped-and-bound template components for this entry.
    """
    components: list[Component] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return False  # Internal container; parent Repeater handles clearing

    @property
    def children(self) -> list[Component]:
        return self.components

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.components)

    def _serialize_state(self) -> dict:
        state = self._base_state()
        state["form"] = "entry"
        state["components"] = [s for ef in self.components if (s := ef.serialize()) is not None]
        return state

    def render_from_data(self, data: dict) -> str:
        from markupsafe import escape as _esc
        html = f'<h4 style="margin: 4px 0;">{_esc(data["label"])}</h4>'
        html += "".join(ef.render_safely() for ef in self.components)
        return html

    def get_affordances(self) -> list[Affordance]:
        return []

    def _handle(self, body: dict) -> dict:
        return self.serialize()


@dataclass
class Repeater(Component):
    """A container that stamps out a template of components per dynamic entry.

    Usage:
        Repeater(key="employees", label="Employees", template=[
            TextForm(key="name", label="Name"),
            ChoiceForm(key="role", label="Role", options=["Dev", "QA", "PM"]),
            DateForm(key="start_date", label="Start Date"),
        ], min_entries=1)
    """
    form = "repeater"

    template: list[Component] = field(default_factory=list)
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
    def children(self) -> list[Component]:
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
                components=stamped,
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
        return self._base_state() | {
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
        affs = data.get("affordances", [])
        remove_affs = {}
        for aff in affs:
            if aff.get("body", {}).get("action") == "remove":
                remove_affs[aff["body"]["id"]] = aff
        entry_items = []
        for idx, eg in enumerate(self._entry_groups):
            entry_id = eg.key
            entry_items.append({"id": entry_id, "index": idx, "label": f"{self.entry_label} {idx + 1}", "html": "".join(ef.render_safely() for ef in eg.components), "remove_body": remove_affs.get(entry_id, {}).get("body")})
        return render_template("repeater.html", data=data, ef=self, url=self.url, entry_label=self.entry_label, entry_count=data.get("entry_count", 0), min_entries=self.min_entries, max_entries=self.max_entries, entry_items=entry_items)

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")
        entries = list(self._entry_ids)
        next_id = self._next_id

        if action == "add":
            if self.max_entries is not None and len(entries) >= self.max_entries:
                return self._error(f"Maximum {self.max_entries} entries reached.", action=action)
            entry_id = f"entry_{next_id}"
            entries.append(entry_id)
            next_id += 1
            self._save_structural(entries, next_id)
            self._rebuild_entries()

        elif action == "remove":
            entry_id = body.get("id", "")
            if entry_id not in entries:
                return self._error(f"Unknown entry: {entry_id}.", action=action)
            # Clear the entry's scope
            entry_scope = f"{self.key}/{entry_id}"
            self._store.clear_scope(entry_scope)
            entries.remove(entry_id)
            self._save_structural(entries, next_id)
            self._rebuild_entries()

        else:
            return self._error(f"Unknown action: {action}", action=action)

        return self.serialize()
