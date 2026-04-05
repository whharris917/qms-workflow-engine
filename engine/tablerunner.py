"""TableRunner — executes a TableForm as a gated sequential workflow.

A Runner reads a sibling eigenform's structure and presents an executable
interface derived from it. TableRunner reads a TableForm and presents its
rows as a gated sequence: each row's cell eigenforms are rendered large,
one row at a time, with navigation gated by the table's ordering constraints.

The TableRunner owns no data. All cell data lives in the source TableForm's
compound scopes. The runner only stores its own navigation state (which row
is currently focused).

    TableForm defines structure  →  TableRunner executes it
    Columns = what to do         →  Cell eigenforms = do it
    Row constraints = gates      →  Gated navigation = enforcement
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.eigenform import Eigenform
from engine.ordered_collection import OrderedCollection
from engine.templates import render_template
from engine.store import Store


@dataclass
class TableRunner(Eigenform):
    """Execute a TableForm as a gated sequential workflow.

    The source TableForm defines the schema (columns, typed columns),
    the rows (stages), and the ordering constraints (gates). The runner
    presents one row at a time, with cell eigenforms rendered large and
    interactive. Rows are accessible only when their prerequisite rows
    are complete.
    """
    source: Any = None  # TableForm instance — set at definition time

    # --- Internal: bound source and cell eigenforms ---

    _bound_source: Any = field(default=None, init=False, repr=False)

    def _bind_children(self, store: Store, url_prefix: str):
        """Bind by creating our own view of the source table's cell eigenforms.

        All columns become eigenforms in the runner — typed columns use the
        table's templates, and text columns become TextForms. This ensures
        every cell in execution mode is a proper eigenform.
        """
        from engine.tableform import TableForm
        if self.source is None or not isinstance(self.source, TableForm):
            return
        # Bind a copy of the source to the same store and scope so it reads
        # the same data.
        bound = self.source.bind(store=store, scope=self._scope,
                                 url_prefix=self._url_prefix)

        # Only typed columns are executable — text columns are authoring-only
        # (they provide row labels but aren't interactive in the runner).
        # Patch cell eigenform URLs to route through the runner.
        runner_url = f"{self._url_prefix}/{self.key}"
        for rg in getattr(bound, '_row_groups', []):
            rg._url_prefix = runner_url
            for col_id, ef in rg.cell_eigenforms.items():
                ef._url_prefix = f"{runner_url}/{rg.key}"
        self._bound_source = bound

    @property
    def _source_table(self):
        return self._bound_source

    @property
    def children(self) -> list[Eigenform]:
        """Expose the source table's RowGroups as children for path-based routing."""
        if self._source_table is None:
            return []
        return self._source_table.children

    # --- Row accessibility (constraint-gated) ---

    def _row_items(self) -> list[dict]:
        if self._source_table is None:
            return []
        return self._source_table._row_collection.items

    def _col_items(self) -> list[dict]:
        if self._source_table is None:
            return []
        return self._source_table._col_collection.items

    def _constraint_graph(self) -> dict[str, list[str]]:
        if self._source_table is None:
            return {}
        return self._source_table._row_collection.effective_must_follow

    def _row_groups_by_id(self) -> dict[str, Any]:
        from engine.tableform import RowGroup
        if self._source_table is None:
            return {}
        return {rg.key: rg for rg in self._source_table.children}

    def _is_row_complete(self, row_id: str) -> bool:
        """A row is complete when all its cell eigenforms are complete."""
        rg = self._row_groups_by_id().get(row_id)
        if rg is None:
            return False
        return all(ef.is_complete for ef in rg.cell_eigenforms.values())

    def _is_row_accessible(self, row_id: str) -> bool:
        """A row is accessible when all its prerequisite rows are complete."""
        mf = self._constraint_graph()
        prereqs = mf.get(row_id, [])
        return all(self._is_row_complete(p) for p in prereqs)

    def _accessible_row_ids(self) -> set[str]:
        return {item["id"] for item in self._row_items() if self._is_row_accessible(item["id"])}

    # --- Navigation state ---

    @property
    def _active_row_id(self) -> str | None:
        stored = self.value
        row_ids = {item["id"] for item in self._row_items()}
        if stored and stored in row_ids:
            return stored
        # Default to first accessible row
        for item in self._row_items():
            if self._is_row_accessible(item["id"]):
                return item["id"]
        return self._row_items()[0]["id"] if self._row_items() else None

    @property
    def is_complete(self) -> bool:
        return all(self._is_row_complete(item["id"]) for item in self._row_items())

    # --- Serialization ---

    def _serialize_state(self) -> dict:
        rows = self._row_items()
        cols = self._col_items()
        accessible = self._accessible_row_ids()
        active = self._active_row_id
        rg_map = self._row_groups_by_id()

        templates = self._source_table._typed_column_templates if self._source_table else {}
        cells_data = self._source_table._cells if self._source_table else {}

        progress = []
        for item in rows:
            rid = item["id"]
            complete = self._is_row_complete(rid)
            # Row label from first text column (authoring data), fall back to row ID
            row_data = cells_data.get(rid, {})
            label = None
            for c in cols:
                if c["id"] not in templates and row_data.get(c["id"]):
                    label = str(row_data[c["id"]])
                    break
            if not label:
                label = item.get("value") or rid
            progress.append({
                "row_id": rid,
                "label": label,
                "complete": complete,
                "accessible": rid in accessible,
            })

        return self._base_state() | {
            "active_row": active,
            "progress": progress,
            "columns": [{"key": c["id"], "label": c["value"]} for c in cols],
        }

    def _serialize_full(self) -> dict:
        state = self._serialize_state()
        state["complete"] = self.is_complete

        # Serialize the active row's cell eigenforms
        active = self._active_row_id
        rg = self._row_groups_by_id().get(active) if active else None

        cell_states = []
        for c in self._col_items():
            col_id = c["id"]
            ef = rg.cell_eigenforms.get(col_id) if rg else None
            cell_states.append({
                "column": c["value"],
                "col_id": col_id,
                "state": ef.serialize() if ef else None,
            })
        state["cells"] = cell_states

        affordances = self.get_affordances()
        state["affordances"] = [a.serialize() for a in affordances]
        return state

    def get_affordances(self) -> list[Affordance]:
        affordances: list[Affordance] = []
        rows = self._row_items()
        if not rows:
            return affordances

        active = self._active_row_id
        accessible = self._accessible_row_ids()
        active_idx = next((i for i, r in enumerate(rows) if r["id"] == active), 0)

        # Back
        if active_idx > 0:
            prev = rows[active_idx - 1]
            affordances.append(SimpleButtonAffordance(
                label=f"\u2190 Back",
                method="POST",
                url=self.url,
                body={"action": "navigate", "row": prev["id"]},
                instruction=f"Go back to {prev['id']}.",
            ))

        # Next (if current row complete and next is accessible)
        if active_idx < len(rows) - 1:
            nxt = rows[active_idx + 1]
            if self._is_row_complete(active) and nxt["id"] in accessible:
                affordances.append(SimpleButtonAffordance(
                    label=f"Next \u2192",
                    method="POST",
                    url=self.url,
                    body={"action": "navigate", "row": nxt["id"]},
                    instruction=f"Advance to {nxt['id']}.",
                ))

        # Jump to completed accessible rows
        completed = {
            item["id"]: item["id"]
            for item in rows
            if item["id"] != active
            and item["id"] in accessible
            and self._is_row_complete(item["id"])
        }
        if completed:
            aff = Affordance(
                label="Go to Row",
                method="POST",
                url=self.url,
                body={"action": "navigate", "row": "<row_id>"},
                instruction="Jump to a completed row.",
            )
            aff._steps = completed
            aff._chrome_rendered = True
            affordances.append(aff)

        return affordances

    # --- Rendering ---

    def render_from_data(self, data: dict) -> str:
        active_row = data.get("active_row")
        progress = data.get("progress", [])
        cells_html = ""
        locked_msg = ""
        if active_row and self._is_row_accessible(active_row):
            rg = self._row_groups_by_id().get(active_row)
            if rg:
                cells_html = "".join(ef.render() for ef in rg.cell_eigenforms.values())
        elif active_row and not self._is_row_accessible(active_row):
            prereqs = self._constraint_graph().get(active_row, [])
            locked_msg = f"This row is locked. Complete prerequisite rows first: {', '.join(prereqs)}."
        return render_template("tablerunner.html", data=data, ef=self, url=self.url, progress=progress, active_row=active_row, cells_html=cells_html, locked_msg=locked_msg)

    # --- Action handling ---

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")
        if action == "navigate":
            row_id = body.get("row", "")
            row_ids = {item["id"] for item in self._row_items()}
            if row_id in row_ids and self._is_row_accessible(row_id):
                self._store.set(self._scope, self.key, row_id)
        return self.serialize()
