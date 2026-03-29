"""TableForm — a tabular eigenform with columns, rows, and cell-level interaction.

A table is a self-contained HATEOAS-compliant application. Its state is a
2D grid of typed cells. Its affordances allow structural operations (add/remove
rows and columns), data operations (set cell values, set entire rows), and
ordering operations (move rows/columns, ordering constraints).

Rows and columns are each managed by an OrderedCollection, giving them stable
IDs, fixed-item support, ordering constraints, and reordering capabilities.
Cell data is managed separately, keyed by stable row/column IDs.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import (
    Affordance, AddConstraintAffordance, SimpleButtonAffordance,
    BUTTON_GAP, STYLE_CONFIRM, STYLE_REMOVE, STYLE_ARROW, render_inline_button,
)
from engine.eigenform import Eigenform
from engine.ordered_collection import OrderedCollection


class SetCellAffordance(Affordance):
    """An affordance that sets a single cell value."""

    def _render_hints(self) -> dict:
        return {"type": "inline_cell"}


class AddColumnAffordance(Affordance):
    """An affordance that adds a column to the table."""

    def _render_hints(self) -> dict:
        return {"type": "text_input_add", "placeholder": "Column name"}


@dataclass
class RowGroup(Eigenform):
    """Lightweight routing node for one row's typed cell eigenforms.

    Created by TableForm._bind_children(). Enables find_eigenform to
    traverse table_key -> row_id -> col_id for path-based access to
    typed cell eigenforms.
    """
    cell_eigenforms: dict[str, Eigenform] = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return False  # Parent TableForm handles clearing

    @property
    def children(self) -> list[Eigenform]:
        return list(self.cell_eigenforms.values())

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.cell_eigenforms.values())

    def _serialize_state(self) -> dict:
        state = self._base_state()
        state["form"] = "row"
        return state

    def render_from_data(self, data: dict) -> str:
        return ""  # Never rendered standalone

    def get_affordances(self) -> list[Affordance]:
        return []

    def _handle(self, body: dict) -> dict:
        return self.serialize()


@dataclass
class TableForm(Eigenform):
    """A table with dynamic columns, stable row IDs, and row-level operations.

    Both rows and columns are backed by OrderedCollection, providing:
    - Stable IDs (row_0, col_0, ...)
    - Fixed items (immutable rows/columns)
    - Ordering constraints (must_follow)
    - Constraint-aware move up/down (rows) and left/right (columns)
    """
    fixed_columns: list[str] = field(default_factory=list)
    fixed_rows: list[dict] = field(default_factory=list)
    row_must_follow: dict[str, list[str]] = field(default_factory=dict)
    col_must_follow: dict[str, list[str]] = field(default_factory=dict)
    allow_row_constraints: bool = False
    allow_col_constraints: bool = False

    # --- Internal state ---

    @property
    def _raw_state(self) -> dict:
        stored = self.value
        if stored and isinstance(stored, dict):
            # Detect legacy format: "row_order" is a flat list of strings
            if "row_order" in stored and isinstance(stored.get("row_order"), list):
                row_order = stored["row_order"]
                if not row_order or isinstance(row_order[0], str):
                    return self._migrate_legacy(stored)
            return stored
        return {}

    def _migrate_legacy(self, old: dict) -> dict:
        """Convert legacy TableForm state to new format."""
        col_items = [{"id": c["key"], "value": c["label"]}
                     for c in old.get("columns", [])]
        row_items = [{"id": rid, "value": ""}
                     for rid in old.get("row_order", [])]
        new = {
            "columns": {"items": col_items, "next_id": old.get("next_col_id", 0)},
            "rows_meta": {"items": row_items, "next_id": old.get("next_row_id", 0)},
            "cells": old.get("rows", {}),
        }
        self._store.set(self._scope, self.key, new)
        return new

    @property
    def _fixed_col_labels(self) -> list[str]:
        """Extract string labels from fixed_columns, handling both str and Eigenform entries."""
        return [c.label if isinstance(c, Eigenform) else c for c in self.fixed_columns]

    @property
    def _typed_column_templates(self) -> dict[str, Eigenform]:
        """Map col_id -> unbound eigenform template for typed columns."""
        return {
            f"col_{i}": c
            for i, c in enumerate(self.fixed_columns)
            if isinstance(c, Eigenform)
        }

    @property
    def _col_collection(self) -> OrderedCollection:
        oc = OrderedCollection(
            id_prefix="col",
            fixed_items=self._fixed_col_labels,
            static_must_follow=self.col_must_follow,
            allow_constraints=self.allow_col_constraints,
        )
        oc.load(self._raw_state.get("columns"))
        return oc

    @property
    def _row_collection(self) -> OrderedCollection:
        oc = OrderedCollection(
            id_prefix="row",
            fixed_items=[],  # fixed_rows handled specially (they carry cell data)
            static_must_follow=self.row_must_follow,
            allow_constraints=self.allow_row_constraints,
        )
        state = self._raw_state.get("rows_meta")
        # Seed fixed rows on first access
        if state is None and self.fixed_rows:
            items = [{"id": f"row_{i}", "value": "", "fixed": True}
                     for i in range(len(self.fixed_rows))]
            state = {"items": items, "next_id": len(self.fixed_rows)}
        # Seed one empty row when columns exist but no rows yet
        elif state is None and self.fixed_columns:
            state = {"items": [{"id": "row_0", "value": ""}], "next_id": 1}
        oc.load(state)
        return oc

    @property
    def _cells(self) -> dict[str, dict]:
        """Cell data: {"row_0": {"col_0": "Alice", ...}, ...}"""
        return self._raw_state.get("cells", {})

    # --- Typed column children ---

    @property
    def children(self) -> list[Eigenform]:
        return list(getattr(self, '_row_groups', []))

    def _bind_children(self, store, url_prefix: str):
        """Create RowGroups with bound cell eigenforms for all typed columns."""
        from engine.store import Store
        self._row_groups: list[RowGroup] = []
        templates = self._typed_column_templates
        if not templates:
            return
        for row_item in self._row_collection.items:
            row_id = row_item["id"]
            row_scope = f"{self.key}/{row_id}"
            row_url = f"{url_prefix}/{self.key}/{row_id}"
            cells = {}
            for col_id, template in templates.items():
                ef = copy.deepcopy(template)
                ef.key = col_id
                bound_ef = ef.bind(store=store, scope=row_scope, url_prefix=row_url)
                cells[col_id] = bound_ef
            group = RowGroup(
                key=row_id, label=row_id,
                cell_eigenforms=cells,
            )
            group._store = store
            group._scope = row_scope
            group._url_prefix = f"{url_prefix}/{self.key}"
            self._row_groups.append(group)

    def _rebuild_rows(self):
        """Rebuild RowGroups after structural mutations."""
        if self._store is not None and self._typed_column_templates:
            self._bind_children(self._store, self._url_prefix)

    # --- Convenience properties ---

    @property
    def columns(self) -> list[dict]:
        """Column definitions: [{"key": "col_0", "label": "Name"}, ...]"""
        return [{"key": i["id"], "label": i["value"]} for i in self._col_collection.items]

    @property
    def col_keys(self) -> list[str]:
        return [i["id"] for i in self._col_collection.items]

    @property
    def col_labels(self) -> dict[str, str]:
        return {i["id"]: i["value"] for i in self._col_collection.items}

    @property
    def row_order(self) -> list[str]:
        return [i["id"] for i in self._row_collection.items]

    @property
    def rows(self) -> dict[str, dict]:
        return self._cells

    # --- Core ---

    def _clear_data(self):
        """Clear all cell data, including typed cell compound scopes."""
        if self._store is not None and self._typed_column_templates:
            for row_item in self._row_collection.items:
                self._store.clear_scope(f"{self.key}/{row_item['id']}")
        super()._clear_data()
        self._rebuild_rows()

    @property
    def is_complete(self) -> bool:
        cols = self._col_collection.items
        rows_meta = self._row_collection.items
        cells = self._cells
        templates = self._typed_column_templates
        row_groups_by_id = {rg.key: rg for rg in getattr(self, '_row_groups', [])}
        if not cols or not rows_meta:
            return False
        for row_item in rows_meta:
            row_id = row_item["id"]
            row = cells.get(row_id, {})
            rg = row_groups_by_id.get(row_id)
            for col_item in cols:
                col_id = col_item["id"]
                if col_id in templates:
                    if rg:
                        ef = rg.cell_eigenforms.get(col_id)
                        if ef is None or not ef.is_complete:
                            return False
                    else:
                        return False
                else:
                    if row.get(col_id) is None:
                        return False
        return True

    @property
    def _config(self) -> dict:
        return self._raw_state.get("config", {})

    def _save(self, col_state: dict, row_state: dict, cells: dict,
              config: dict | None = None):
        state = {
            "columns": col_state,
            "rows_meta": row_state,
            "cells": cells,
        }
        cfg = config if config is not None else self._config
        if cfg:
            state["config"] = cfg
        self._store.set(self._scope, self.key, state)

    def _apply_auto_chain(self, state: dict, key: str, config: dict | None = None) -> dict:
        """If auto_chain is on for the given axis, rebuild constraints as a sequential chain."""
        cfg = config if config is not None else self._config
        if not cfg.get(key):
            return state
        items = state.get("items", [])
        if len(items) < 2:
            state.pop("constraints", None)
            return state
        constraints = []
        for i in range(1, len(items)):
            constraints.append({"item": items[i]["id"], "after": items[i - 1]["id"]})
        state["constraints"] = constraints
        return state

    def _current_states(self) -> tuple[dict, dict, dict]:
        """Return current col_state, row_state, cells as mutable copies.

        Builds state from the collections (which handle seeding of
        fixed items) rather than reading raw from the store.
        """
        col_oc = self._col_collection
        row_oc = self._row_collection
        col_state: dict = {"items": [dict(i) for i in col_oc.items], "next_id": col_oc.next_id}
        if col_oc.stored_constraints:
            col_state["constraints"] = list(col_oc.stored_constraints)
        row_state: dict = {"items": [dict(i) for i in row_oc.items], "next_id": row_oc.next_id}
        if row_oc.stored_constraints:
            row_state["constraints"] = list(row_oc.stored_constraints)
        cells = {k: dict(v) for k, v in self._cells.items()}
        return col_state, row_state, cells

    def _resolve_column(self, ref: str) -> str | None:
        """Resolve a column reference — accepts key or label."""
        col_oc = self._col_collection
        for item in col_oc.items:
            if item["id"] == ref:
                return ref
        for item in col_oc.items:
            if item["value"] == ref:
                return item["id"]
        return None

    def _serialize_state(self) -> dict:
        row_oc = self._row_collection
        col_oc = self._col_collection
        cells = self._cells
        templates = self._typed_column_templates
        row_groups_by_id = {rg.key: rg for rg in getattr(self, '_row_groups', [])}

        ordered_rows = []
        for row_item in row_oc.items:
            row_id = row_item["id"]
            row_data = {"_id": row_id}
            cell_data = cells.get(row_id, {})
            rg = row_groups_by_id.get(row_id)
            for col_item in col_oc.items:
                col_id = col_item["id"]
                if col_id in templates and rg:
                    ef = rg.cell_eigenforms.get(col_id)
                    row_data[col_id] = ef.serialize() if ef else None
                else:
                    row_data[col_id] = cell_data.get(col_id)
            ordered_rows.append(row_data)

        # Mark typed columns in column list
        columns = []
        for item in col_oc.items:
            col = {"key": item["id"], "label": item["value"]}
            if item["id"] in templates:
                col["typed"] = True
                col["form"] = templates[item["id"]].form
            columns.append(col)

        return self._base_state() | {
            "columns": columns,
            "rows": ordered_rows,
            "summary": f"{len(col_oc.items)} {'column' if len(col_oc.items) == 1 else 'columns'}, {len(row_oc.items)} {'row' if len(row_oc.items) == 1 else 'rows'}",
        }

    def get_affordances(self) -> list[Affordance]:
        affordances: list[Affordance] = []
        col_oc = self._col_collection
        row_oc = self._row_collection
        col_items = col_oc.items
        row_items = row_oc.items
        templates = self._typed_column_templates
        text_col_items = [i for i in col_items if i["id"] not in templates]
        text_col_keys_str = " | ".join(i["id"] for i in text_col_items) if text_col_items else ""
        row_ids_str = " | ".join(i["id"] for i in row_items) if row_items else ""

        # Add column
        fixed_col_ids = {i["id"] for i in col_items if i.get("fixed")}
        affordances.append(AddColumnAffordance(
            label="+ Column",
            method="POST",
            url=self.url,
            body={"action": "add_column", "label": "<column name>"},
            instruction="Add a new column. Provide the column label.",
        ))

        # Rename column (editable columns only)
        editable_cols = [i for i in col_items if not i.get("fixed")]
        if editable_cols:
            editable_col_keys = " | ".join(i["id"] for i in editable_cols)
            affordances.append(Affordance(
                label="Rename Column",
                method="POST",
                url=self.url,
                body={"action": "rename_column", "column": f"<{editable_col_keys}>", "label": "<new label>"},
                instruction="Rename a column. Accepts column key or current label.",
            ))

        # Add row (with optional initial values for text columns only)
        if col_items:
            text_desc = ", ".join(f"{i['id']} ({i['value']})" for i in text_col_items)
            add_row_body: dict[str, Any] = {"action": "add_row"}
            for i in text_col_items:
                add_row_body[i["id"]] = f"<{i['value']}>"
            instruction = "Add a new row."
            if text_col_items:
                instruction += f" Optionally include text column keys with values: {text_desc}. Omitted columns default to empty."
            if templates:
                typed_desc = ", ".join(
                    f"{cid} ({templates[cid].label} — {templates[cid].form})"
                    for cid in sorted(templates)
                )
                instruction += f" Typed columns ({typed_desc}) are set via their own cell URLs after row creation."
            affordances.append(Affordance(
                label="+ Row",
                method="POST",
                url=self.url,
                body=add_row_body,
                instruction=instruction,
            ))

        # Set cell (text columns only)
        if text_col_items and row_items:
            affordances.append(SetCellAffordance(
                label="Set Cell",
                method="POST",
                url=self.url,
                body={"action": "set_cell", "row": f"<{row_ids_str}>", "column": f"<{text_col_keys_str}>", "value": "<value>"},
                instruction="Set a text cell value. Row is a row ID. Column is a key or label. Typed columns are set via their own cell URLs.",
            ))

        # Set row (text columns only)
        if text_col_items and row_items:
            body: dict[str, Any] = {"action": "set_row", "row": f"<{row_ids_str}>"}
            for item in text_col_items:
                body[item["id"]] = f"<{item['value']} value>"
            affordances.append(Affordance(
                label="Set Row",
                method="POST",
                url=self.url,
                body=body,
                instruction="Set multiple cells in a row at once. Omitted columns are unchanged.",
            ))

        # Move row up/down
        if len(row_items) > 1:
            can_up = [row_items[i]["id"] for i in range(len(row_items))
                      if row_oc.can_move_up(i, row_items)]
            can_down = [row_items[i]["id"] for i in range(len(row_items))
                        if row_oc.can_move_down(i, row_items)]
            if can_up:
                affordances.append(Affordance(
                    label="Move Row Up",
                    method="POST",
                    url=self.url,
                    body={"action": "move_row_up", "row": f"<{' | '.join(can_up)}>"},
                    instruction="Move a row up one position.",
                ))
            if can_down:
                affordances.append(Affordance(
                    label="Move Row Down",
                    method="POST",
                    url=self.url,
                    body={"action": "move_row_down", "row": f"<{' | '.join(can_down)}>"},
                    instruction="Move a row down one position.",
                ))

        # Move column left/right
        if len(col_items) > 1:
            can_left = [col_items[i]["id"] for i in range(len(col_items))
                        if col_oc.can_move_up(i, col_items)]
            can_right = [col_items[i]["id"] for i in range(len(col_items))
                         if col_oc.can_move_down(i, col_items)]
            if can_left:
                affordances.append(Affordance(
                    label="Move Column Left",
                    method="POST",
                    url=self.url,
                    body={"action": "move_col_left", "column": f"<{' | '.join(can_left)}>"},
                    instruction="Move a column one position to the left.",
                ))
            if can_right:
                affordances.append(Affordance(
                    label="Move Column Right",
                    method="POST",
                    url=self.url,
                    body={"action": "move_col_right", "column": f"<{' | '.join(can_right)}>"},
                    instruction="Move a column one position to the right.",
                ))

        # Row constraints
        if self.allow_row_constraints and len(row_items) > 1:
            r_ids = [i["id"] for i in row_items]
            r_labels = {i["id"]: i["value"] or i["id"] for i in row_items}
            affordances.append(AddConstraintAffordance(
                label="Add Row Constraint",
                method="POST",
                url=self.url,
                body={"action": "add_row_constraint", "item": f"<{' | '.join(r_ids)}>", "after": f"<{' | '.join(r_ids)}>"},
                instruction=f"Require that <item> row must appear after <after> row.",
                item_values=r_ids,
                item_labels=r_labels,
            ))
        row_dynamic = row_oc.stored_constraints
        if row_dynamic:
            pairs = " | ".join(f"{c['item']} after {c['after']}" for c in row_dynamic)
            affordances.append(Affordance(
                label="Remove Row Constraint",
                method="POST",
                url=self.url,
                body={"action": "remove_row_constraint", "item": f"<{pairs}>", "after": f"<see pairs>"},
                instruction=f"Remove a dynamic row ordering constraint. Active: {pairs}.",
            ))

        # Column constraints
        if self.allow_col_constraints and len(col_items) > 1:
            c_ids = [i["id"] for i in col_items]
            c_labels = {i["id"]: i["value"] for i in col_items}
            affordances.append(AddConstraintAffordance(
                label="Add Column Constraint",
                method="POST",
                url=self.url,
                body={"action": "add_col_constraint", "item": f"<{' | '.join(c_ids)}>", "after": f"<{' | '.join(c_ids)}>"},
                instruction=f"Require that <item> column must appear after <after> column.",
                item_values=c_ids,
                item_labels=c_labels,
            ))
        col_dynamic = col_oc.stored_constraints
        if col_dynamic:
            pairs = " | ".join(f"{c['item']} after {c['after']}" for c in col_dynamic)
            affordances.append(Affordance(
                label="Remove Column Constraint",
                method="POST",
                url=self.url,
                body={"action": "remove_col_constraint", "item": f"<{pairs}>", "after": f"<see pairs>"},
                instruction=f"Remove a dynamic column ordering constraint. Active: {pairs}.",
            ))

        # Remove row (editable rows only)
        editable_rows = [i for i in row_items if not i.get("fixed")]
        if editable_rows:
            editable_row_ids = " | ".join(i["id"] for i in editable_rows)
            affordances.append(Affordance(
                label="Remove Row",
                method="POST",
                url=self.url,
                body={"action": "remove_row", "row": f"<{editable_row_ids}>"},
                instruction="Remove a row by ID.",
            ))

        # Remove column (editable columns only)
        if editable_cols:
            editable_col_keys_str = " | ".join(i["id"] for i in editable_cols)
            affordances.append(Affordance(
                label="Remove Column",
                method="POST",
                url=self.url,
                body={"action": "remove_column", "column": f"<{editable_col_keys_str}>"},
                instruction="Remove a column by key or label.",
            ))

        # Auto-chain toggles
        if self.allow_row_constraints:
            on = self._config.get("auto_chain_rows", False)
            affordances.append(Affordance(
                label="Toggle Auto-Chain Rows",
                method="POST",
                url=self.url,
                body={"action": "toggle_auto_chain_rows"},
                instruction=f"Toggle automatic sequential row chaining (currently {'on' if on else 'off'}). When on, each row automatically depends on the previous one.",
            ))
        if self.allow_col_constraints:
            on = self._config.get("auto_chain_cols", False)
            affordances.append(Affordance(
                label="Toggle Auto-Chain Columns",
                method="POST",
                url=self.url,
                body={"action": "toggle_auto_chain_cols"},
                instruction=f"Toggle automatic sequential column chaining (currently {'on' if on else 'off'}). When on, each column automatically depends on the previous one.",
            ))

        return affordances

    @staticmethod
    def _render_constraint_dropdown(
        url: str, item_id: str, prereqs: list[str],
        all_items: list[dict], add_action: str,
    ) -> str:
        """Render the + Prerequisite dropdown for a single item."""
        available = [i for i in all_items if i["id"] != item_id and i["id"] not in prereqs]
        if not available:
            return ''
        def _opt(i: dict) -> str:
            body = json.dumps({"action": add_action, "item": item_id, "after": i["id"]})
            label = i["value"] + " (" + i["id"] + ")" if i["value"] else i["id"]
            return (
                f'<option value="{escape(i["id"])}"'
                f' title="POST {url} {escape(body)}">'
                f'{escape(label)}</option>'
            )
        add_opts = "".join(_opt(i) for i in available)
        return (
            f'<span style="position: relative; display: inline-block;'
            f' width: 24px; height: 24px; box-sizing: content-box;'
            f' border: 1px solid #ccc; background: #f8f8f8; vertical-align: middle;">'
            f'<span style="position: absolute; inset: 0; display: flex;'
            f' align-items: center; justify-content: center;'
            f' font-size: 18px; font-weight: normal; pointer-events: none;">☑</span>'
            f'<select title="POST {url} {{&quot;action&quot;:&quot;{add_action}&quot;,&quot;item&quot;:&quot;{item_id}&quot;,&quot;after&quot;:&quot;...&quot;}}"'
            f' style="position: absolute; inset: 0; width: 100%; height: 100%;'
            f' opacity: 0; cursor: pointer;" onchange="'
            f"if(this.value)fetch('{url}',"
            f"{{method:'POST',headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify({{action:'{add_action}',item:'{item_id}',after:this.value}})"
            f"}}).then(()=>location.reload())"
            f'">'
            f'<option value="">—</option>'
            f'{add_opts}'
            f'</select>'
            f'</span>'
        )

    @staticmethod
    def _render_constraint_pills(
        url: str, item_id: str, prereqs: list[str],
        id_to_val: dict[str, str], static_pairs: set[tuple[str, str]],
        remove_action: str, pill_bg: str,
    ) -> str:
        """Render prerequisite pills with remove buttons for a single item."""
        if not prereqs:
            return ''
        html = '<span style="display: inline-flex; flex-direction: column; gap: 2px;">'
        for p_id in prereqs:
            p_name = escape(id_to_val.get(p_id, p_id) or p_id)
            is_static = (item_id, p_id) in static_pairs
            html += '<span style="display: inline-flex; align-items: center; gap: 2px;">'
            html += (
                f'<span style="display: inline-block; min-width: 52px; color: #666;'
                f' text-align: center; background: #e8e8e8; border-radius: 10px;'
                f' padding: 1px 6px; font-family: monospace; font-size: 0.85em;">'
                f'{p_name}</span>'
            )
            if not is_static:
                html += render_inline_button(
                    url, {"action": remove_action, "item": item_id, "after": p_id},
                    "x", STYLE_REMOVE,
                )
            html += '</span>'
        html += '</span>'
        return html

    @staticmethod
    def _render_constraint_inline(
        url: str, item_id: str, prereqs: list[str],
        id_to_val: dict[str, str], static_pairs: set[tuple[str, str]],
        all_items: list[dict], add_action: str, remove_action: str,
        pill_bg: str,
    ) -> str:
        """Render inline constraint dropdown + prerequisite pills (for column constraints)."""
        html = '<span style="display: inline-flex; flex-direction: column; align-items: center; gap: 2px;">'
        html += TableForm._render_constraint_dropdown(url, item_id, prereqs, all_items, add_action)
        html += TableForm._render_constraint_pills(url, item_id, prereqs, id_to_val, static_pairs, remove_action, pill_bg)
        html += '</span>'
        return html

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        col_oc = self._col_collection
        row_oc = self._row_collection
        col_items = col_oc.items
        row_items = row_oc.items
        templates = self._typed_column_templates
        row_groups_by_id = {rg.key: rg for rg in getattr(self, '_row_groups', [])}

        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        # Configuration panel
        config = self._config
        config_toggles = []
        url_for_config = data.get("affordances", [{}])[0].get("url", "")
        if self.allow_row_constraints:
            config_toggles.append(("auto_chain_rows", "toggle_auto_chain_rows", "Auto-chain rows"))
        if self.allow_col_constraints:
            config_toggles.append(("auto_chain_cols", "toggle_auto_chain_cols", "Auto-chain columns"))
        if config_toggles:
            html += (
                f'<div style="background: #f8f8f8; border: 1px solid #ddd; border-radius: 4px;'
                f' padding: 6px 10px; margin: 8px 0; display: inline-flex; align-items: center; gap: 12px;">'
                f'<span style="font-weight: bold; font-size: 0.9em; color: #555;">Configuration</span>'
            )
            for cfg_key, action_name, label in config_toggles:
                checked = ' checked' if config.get(cfg_key, False) else ''
                toggle_body = json.dumps({"action": action_name})
                html += (
                    f'<label style="display: inline-flex; align-items: center; gap: 4px; cursor: pointer;">'
                    f'<input type="checkbox"{checked} onchange="fetch(\'{url_for_config}\','
                    f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                    f'body:JSON.stringify({toggle_body.replace(chr(34), "&quot;")})}}).then(()=>location.reload())"'
                    f' title="POST {url_for_config} {escape(toggle_body)}" />'
                    f'<span>{label}</span>'
                    f'</label>'
                )
            html += '</div>'

        columns = data.get("columns", [])
        rows = data.get("rows", [])
        affs = data.get("affordances", [])

        url = affs[0]["url"] if affs else ""
        gap = BUTTON_GAP
        num_rows = len(row_items)
        num_cols = len(col_items)

        # Constraint display data
        show_row_constraints = self.allow_row_constraints and num_rows > 0
        show_col_constraints = self.allow_col_constraints and num_cols > 1
        row_mf = row_oc.effective_must_follow if show_row_constraints else {}
        col_mf = col_oc.effective_must_follow if show_col_constraints else {}
        row_id_to_val = row_oc.id_to_value
        col_id_to_val = col_oc.id_to_value
        row_static_pairs = {(iid, aid)
                            for iid, aids in self.row_must_follow.items()
                            for aid in aids} if show_row_constraints else set()
        any_row_prereqs = any(row_mf.get(i["id"]) for i in row_items) if show_row_constraints else False
        col_static_pairs = {(iid, aid)
                            for iid, aids in self.col_must_follow.items()
                            for aid in aids} if show_col_constraints else set()

        if columns:
            add_col_aff = next((a for a in affs if a.get("body", {}).get("action") == "add_column"), None)
            add_row_aff = next((a for a in affs if a.get("body", {}).get("action") == "add_row"), None)

            html += '<div style="overflow-x: auto; margin: 8px 0;"><table style="border-collapse: collapse; white-space: nowrap; width: max-content;">'

            # Header row — empty control cell + ID + data columns
            html += '<tr>'
            ctrl_th = '<th style="border: 1px solid #ccc; padding: 2px 4px; background: #f0f0f0;"></th>'
            html += ctrl_th  # remove column
            if num_rows > 1:
                html += ctrl_th + ctrl_th  # up / down columns
            if show_row_constraints:
                html += ctrl_th  # + Prerequisite column
            html += '<th style="border: 1px solid #ccc; padding: 4px 8px; background: #f0f0f0;">ID</th>'
            if any_row_prereqs:
                html += '<th style="border: 1px solid #ccc; padding: 4px 8px; background: #f0f0f0;">Prerequisites</th>'

            for ci, col in enumerate(columns):
                col_item = col_items[ci] if ci < len(col_items) else None
                col_id = col["key"]
                is_fixed_col = col_item.get("fixed", False) if col_item else False

                # Column move arrows (separate left/right for flanking the pill)
                left_arrow = gap
                right_arrow = gap
                if num_cols > 1:
                    if col_oc.can_move_up(ci, col_items):
                        left_arrow = render_inline_button(url, {"action": "move_col_left", "column": col_id}, "&#9664;", STYLE_ARROW)
                    if col_oc.can_move_down(ci, col_items):
                        right_arrow = render_inline_button(url, {"action": "move_col_right", "column": col_id}, "&#9654;", STYLE_ARROW)

                rm_col_btn = ''
                if not is_fixed_col:
                    rm_col_btn = render_inline_button(url, {"action": "remove_column", "column": col_id}, "\u2212", STYLE_REMOVE)

                # Column constraint row (if enabled)
                constraint_row = ''
                if show_col_constraints:
                    prereqs = col_mf.get(col_id, [])
                    if prereqs or len(col_items) > 1:
                        constraint_row = (
                            f'<div style="display: flex; align-items: center; justify-content: center; padding: 2px 4px 0 4px; border-top: 1px solid #e0e0e0;">'
                            + self._render_constraint_inline(
                                url, col_id, prereqs, col_id_to_val, col_static_pairs,
                                col_items, "add_col_constraint", "remove_col_constraint",
                                "#e8e8f4")
                            + '</div>'
                        )

                # Pill badge style (matches ListForm id_style)
                col_pill = (
                    f'<span style="display: inline-block; min-width: 52px; color: #666;'
                    f' text-align: center; background: #e8e8e8; border-radius: 10px;'
                    f' padding: 1px 6px; font-family: monospace; font-size: 0.85em;">'
                    f'{escape(col_id)}</span>'
                )

                rm_or_gap = rm_col_btn if rm_col_btn else gap

                # ID row: 3-column grid — left arrow | centered pill | right arrow
                id_row = (
                    f'<div style="display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; padding: 2px 4px;">'
                    f'<div style="text-align: left;">{left_arrow}</div>'
                    f'<div>{col_pill}</div>'
                    f'<div style="text-align: right;">{right_arrow}</div>'
                    f'</div>'
                )

                th_style = 'border: 1px solid #ccc; padding: 2px; background: #f0f0f0; vertical-align: top;'

                if is_fixed_col:
                    html += (
                        f'<th style="{th_style}">'
                        f'{id_row}'
                        f'<div style="display: flex; align-items: center; padding: 2px 4px; gap: 4px;">'
                        f'{rm_or_gap}'
                        f'<span style="flex: 1; font-weight: bold; text-align: center; color: #555;">'
                        f'{escape(col["label"])}</span>'
                        f'{gap}'
                        f'</div>'
                        f'{constraint_row}'
                        f'</th>'
                    )
                else:
                    rename_body = {"action": "rename_column", "column": col_id, "label": col["label"]}
                    rename_tooltip = f'POST {url} {escape(json.dumps(rename_body))}'
                    html += (
                        f'<th style="{th_style}">'
                        f'{id_row}'
                        f'<div style="display: flex; align-items: center; padding: 2px 4px; gap: 4px;">'
                        f'{rm_or_gap}'
                        f'<form style="margin:0; flex: 1;" onsubmit="fetch(\'{url}\','
                        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                        f'body:JSON.stringify({{action:\'rename_column\',column:\'{col_id}\','
                        f'label:this.elements.v.value}})'
                        f'}}).then(()=>location.reload()); return false">'
                        f'<input name="v" type="text" value="{escape(col["label"])}" size="12"'
                        f' style="border: 1px solid #ddd; padding: 2px 4px; width: 100%; box-sizing: border-box;'
                        f' font-family: inherit; font-size: inherit;'
                        f' font-weight: bold; text-align: center; color: #555;"'
                        f' oninput="this.nextElementSibling.title='
                        f"'POST {url} '+JSON.stringify({{action:'rename_column',column:'{col_id}',label:this.value}})"
                        f'" />'
                        f'</form>'
                        f'<button style="{STYLE_CONFIRM}"'
                        f' title="{rename_tooltip}"'
                        f' onclick="this.closest(\'th\').querySelector(\'form\').requestSubmit(); return false;"'
                        f'>&#10003;</button>'
                        f'</div>'
                        f'{constraint_row}'
                        f'</th>'
                    )

            # +Column as last header cell
            if add_col_aff:
                add_col_body_preview = json.dumps({"action": "add_column", "label": ""})
                add_col_tooltip = f'POST {url} {escape(add_col_body_preview)}'
                html += (
                    f'<th style="{th_style}">'
                    f'<div style="padding: 2px 4px;">{gap}</div>'
                    f'<div style="display: flex; align-items: center; padding: 2px 4px; gap: 4px;">'
                    f'<form style="margin:0; flex: 1;" onsubmit="fetch(\'{url}\','
                    f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                    f'body:JSON.stringify({{action:\'add_column\',label:this.elements.v.value}})'
                    f'}}).then(()=>location.reload()); return false">'
                    f'<input name="v" type="text" placeholder="Column name" size="12"'
                    f' style="border: 1px solid #ddd; padding: 2px 4px; width: 100%; box-sizing: border-box;'
                    f' font-family: inherit; font-size: inherit;'
                    f' font-weight: bold; text-align: center; color: #555;"'
                    f' oninput="this.title=\'POST {url} \'+JSON.stringify({{action:\'add_column\',label:this.value}})"'
                    f' title="{add_col_tooltip}" />'
                    f'</form>'
                    f'<button style="{STYLE_CONFIRM}"'
                    f' title="{add_col_tooltip}"'
                    f' onclick="this.closest(\'th\').querySelector(\'form\').requestSubmit(); return false;"'
                    f'>+</button>'
                    f'</div>'
                    f'</th>'
                )
            html += '</tr>'

            # Data rows — control cell + ID cell + data cells
            for ri, row_data in enumerate(rows):
                row_id = row_data["_id"]
                row_item = row_items[ri] if ri < len(row_items) else None
                is_fixed_row = row_item.get("fixed", False) if row_item else False

                html += '<tr>'

                # Remove cell (left of grid)
                html += '<td style="border: 1px solid #ccc; padding: 2px 4px; text-align: center; background: #f0f0f0;">'
                if not is_fixed_row:
                    rm_row_body = {"action": "remove_row", "row": row_id}
                    html += render_inline_button(url, rm_row_body, "\u2212", STYLE_REMOVE)
                else:
                    html += gap
                html += '</td>'

                # Up / down arrow columns
                ctrl_td = 'border: 1px solid #ccc; padding: 2px 4px; text-align: center; background: #f0f0f0;'
                if num_rows > 1:
                    if row_oc.can_move_up(ri, row_items):
                        html += f'<td style="{ctrl_td}">' + render_inline_button(url, {"action": "move_row_up", "row": row_id}, "&#9650;", STYLE_ARROW) + '</td>'
                    else:
                        html += f'<td style="{ctrl_td}">{gap}</td>'
                    if row_oc.can_move_down(ri, row_items):
                        html += f'<td style="{ctrl_td}">' + render_inline_button(url, {"action": "move_row_down", "row": row_id}, "&#9660;", STYLE_ARROW) + '</td>'
                    else:
                        html += f'<td style="{ctrl_td}">{gap}</td>'

                # + Prerequisite dropdown column
                if show_row_constraints:
                    prereqs = row_mf.get(row_id, [])
                    dropdown_html = self._render_constraint_dropdown(
                        url, row_id, prereqs, row_items, "add_row_constraint")
                    html += (
                        f'<td style="border: 1px solid #ccc; padding: 4px 8px; white-space: nowrap; background: #f0f0f0;">'
                        f'{dropdown_html}'
                        f'</td>'
                    )

                # ID cell
                row_pill = (
                    f'<span style="display: inline-block; min-width: 52px; color: #666;'
                    f' text-align: center; background: #e8e8e8; border-radius: 10px;'
                    f' padding: 1px 6px; font-family: monospace; font-size: 0.85em;">'
                    f'{escape(row_id)}</span>'
                )
                html += (
                    f'<td style="border: 1px solid #ccc; padding: 4px 8px; white-space: nowrap; text-align: center;">'
                    f'{row_pill}'
                    f'</td>'
                )
                if any_row_prereqs:
                    prereqs = row_mf.get(row_id, [])
                    pills_html = self._render_constraint_pills(
                        url, row_id, prereqs, row_id_to_val, row_static_pairs,
                        "remove_row_constraint", "#e8f4e8")
                    html += (
                        f'<td style="border: 1px solid #ccc; padding: 4px 8px; white-space: nowrap;">'
                        f'{pills_html}'
                        f'</td>'
                    )

                rg = row_groups_by_id.get(row_id)
                for col in columns:
                    col_id = col["key"]
                    if col_id in templates and rg:
                        # Typed cell — render the eigenform inline
                        ef = rg.cell_eigenforms.get(col_id)
                        if ef:
                            html += (
                                f'<td style="border: 1px solid #ccc; padding: 4px; vertical-align: top;">'
                                f'{ef.render()}'
                                f'</td>'
                            )
                        else:
                            html += '<td style="border: 1px solid #ccc; padding: 2px;"></td>'
                    else:
                        # Text cell — inline input
                        cell_value = row_data.get(col_id)
                        display = escape(str(cell_value)) if cell_value is not None else ""
                        cell_val_escaped = escape(str(cell_value)) if cell_value is not None else ""

                        html += (
                            f'<td style="border: 1px solid #ccc; padding: 2px;">'
                            f'<form style="margin:0" onsubmit="fetch(\'{url}\','
                            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                            f'body:JSON.stringify({{action:\'set_cell\',row:\'{row_id}\','
                            f'column:\'{col_id}\',value:this.elements.v.value}})'
                            f'}}).then(()=>location.reload()); return false">'
                            f'<input name="v" type="text" value="{display}"'
                            f' style="border: none; width: 100%; box-sizing: border-box; padding: 2px 4px;"'
                            f' oninput="this.title=\'POST {url} \'+JSON.stringify({{action:\'set_cell\',row:\'{row_id}\',column:\'{col_id}\',value:this.value}})"'
                            f' title="POST {url} {escape(json.dumps({"action": "set_cell", "row": row_id, "column": col_id, "value": cell_val_escaped}))}" />'
                            f'</form>'
                            f'</td>'
                        )
                if add_col_aff:
                    html += '<td style="border: 1px solid #ccc;"></td>'
                html += '</tr>'

            # +Row button row
            if add_row_aff:
                add_row_body = json.dumps({"action": "add_row"})
                html += (
                    f'<tr>'
                    f'<td style="border: 1px solid #ccc; padding: 2px 4px; text-align: center; background: #f0f0f0;">'
                    f'<button onclick="fetch(\'{url}\','
                    f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                    f'body:JSON.stringify({add_row_body.replace(chr(34), "&quot;")})}}).then(()=>location.reload())"'
                    f' style="{STYLE_CONFIRM}"'
                    f' title="POST {url} {escape(add_row_body)}">+</button>'
                    f'</td>'
                    + (f'<td style="border: 1px solid #ccc; background: #f0f0f0;"></td><td style="border: 1px solid #ccc; background: #f0f0f0;"></td>' if num_rows > 1 else '')
                    + (f'<td style="border: 1px solid #ccc; background: #f0f0f0;"></td>' if show_row_constraints else '')
                    + f'<td style="border: 1px solid #ccc; background: #f0f0f0;"></td>'
                    + (f'<td style="border: 1px solid #ccc; background: #f0f0f0;"></td>' if any_row_prereqs else '')
                )
                for _ in columns:
                    html += '<td style="border: 1px solid #ccc; background: #f0f0f0;"></td>'
                if add_col_aff:
                    html += '<td style="border: 1px solid #ccc; background: #f0f0f0;"></td>'
                html += '</tr>'

            html += '</table></div>'
        else:
            # Empty table — show just the +Column input
            add_col_aff = next((a for a in affs if a.get("body", {}).get("action") == "add_column"), None)
            if add_col_aff:
                add_col_body_preview = json.dumps({"action": "add_column", "label": ""})
                html += (
                    f'<table style="border-collapse: collapse; margin: 8px 0;">'
                    f'<tr>'
                    f'<th style="border: 1px solid #ccc; padding: 2px; background: #f0f0f0;">'
                    f'<form style="margin:0; display: flex; align-items: center;" onsubmit="fetch(\'{url}\','
                    f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                    f'body:JSON.stringify({{action:\'add_column\',label:this.elements.v.value}})'
                    f'}}).then(()=>location.reload()); return false">'
                    f'<input name="v" type="text" placeholder="Column name" size="12"'
                    f' style="border: 1px solid #ddd; width: 100px; padding: 2px 4px;"'
                    f' oninput="this.title=\'POST {url} \'+JSON.stringify({{action:\'add_column\',label:this.value}})"'
                    f' title="POST {url} {escape(add_col_body_preview)}" />'
                    f' <button type="submit" style="cursor: pointer; border: none; background: none; color: #2a2;'
                    f' font-size: 14px; font-weight: bold; padding: 0 4px; line-height: 1;"'
                    f' title="POST {url} {escape(add_col_body_preview)}">+</button>'
                    f'</form>'
                    f'</th>'
                    f'</tr>'
                    f'</table></div>'
                )

        if columns and not rows:
            html += '<p style="color: #888;">No rows yet. Add a row to start entering data.</p>'

        # Mark affordances rendered inline in the table
        for aff in affs:
            hints_type = aff.get("render_hints", {}).get("type", "")
            action = aff.get("body", {}).get("action", "")
            if hints_type == "inline_cell" or action in (
                "rename_column", "remove_column", "remove_row", "add_row", "add_column",
                "move_row_up", "move_row_down", "move_col_left", "move_col_right",
                "add_row_constraint", "remove_row_constraint",
                "add_col_constraint", "remove_col_constraint",
                "set_row", "toggle_auto_chain_rows", "toggle_auto_chain_cols",
            ):
                Eigenform.mark_rendered(aff)

        # Remaining affordance controls
        html += '<div style="margin-top: 8px;">'
        for aff in affs:
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        html += '</div>'

        return html

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")
        col_oc = self._col_collection
        row_oc = self._row_collection
        col_state, row_state, cells = self._current_states()
        templates = self._typed_column_templates

        if action == "add_column":
            label = body.get("label", "").strip()
            if not label:
                return self._error("Column label is required.", action=action)
            try:
                col_state = col_oc.add(label)
            except ValueError as e:
                return self._error(str(e), action=action)
            # Seed one empty row if this is the first column
            if not row_state.get("items"):
                row_state = row_oc.add("")
            # Initialize cells for new column (text columns only)
            new_col_id = col_state["items"][-1]["id"]
            for row_id in [i["id"] for i in row_state.get("items", [])]:
                cells.setdefault(row_id, {})[new_col_id] = None
            col_state = self._apply_auto_chain(col_state, "auto_chain_cols")
            self._save(col_state, row_state, cells)

        elif action == "rename_column":
            col_ref = body.get("column", "")
            new_label = body.get("label", "").strip()
            col_key = self._resolve_column(col_ref)
            if not col_key:
                return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action=action)
            if not new_label:
                return self._error("New label is required.", action=action)
            try:
                col_state = col_oc.edit(col_key, new_label)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._save(col_state, row_state, cells)

        elif action == "add_row":
            try:
                row_state = row_oc.add("")
            except ValueError as e:
                return self._error(str(e), action=action)
            new_row_id = row_state["items"][-1]["id"]
            row = {}
            for col_item in col_state.get("items", []):
                col_key = col_item["id"]
                if col_key in templates:
                    continue  # Typed columns managed via cell eigenform URLs
                val = body.get(col_key)
                if val is None:
                    val = body.get(col_item.get("value", ""))
                row[col_key] = val
            cells[new_row_id] = row
            row_state = self._apply_auto_chain(row_state, "auto_chain_rows")
            self._save(col_state, row_state, cells)
            self._rebuild_rows()

        elif action == "set_cell":
            row_id = body.get("row", "")
            col_ref = body.get("column", "")
            value = body.get("value")
            if row_id not in cells and row_id not in {i["id"] for i in row_state.get("items", [])}:
                return self._error(f"Unknown row: {row_id}. Valid: {', '.join(i['id'] for i in row_state.get('items', []))}", action=action)
            col_key = self._resolve_column(col_ref)
            if not col_key:
                return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action=action)
            if col_key in templates:
                return self._error(
                    f"Column '{col_key}' is a typed column ({templates[col_key].form}). "
                    f"Use its cell URL instead: {self.url}/<row_id>/{col_key}",
                    action=action,
                )
            cells.setdefault(row_id, {})[col_key] = value
            self._save(col_state, row_state, cells)

        elif action == "set_row":
            row_id = body.get("row", "")
            row_ids = {i["id"] for i in row_state.get("items", [])}
            if row_id not in row_ids:
                return self._error(f"Unknown row: {row_id}. Valid: {', '.join(row_ids)}", action=action)
            for col_item in col_state.get("items", []):
                col_key = col_item["id"]
                if col_key in templates:
                    continue  # Typed columns managed via cell eigenform URLs
                val = body.get(col_key)
                if val is None:
                    val = body.get(col_item.get("value", ""))
                if val is not None:
                    cells.setdefault(row_id, {})[col_key] = val
            self._save(col_state, row_state, cells)

        elif action == "remove_row":
            row_id = body.get("row", "")
            # Clear typed cell compound scopes before removing
            if templates and self._store:
                self._store.clear_scope(f"{self.key}/{row_id}")
            try:
                row_state = row_oc.remove(row_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            cells.pop(row_id, None)
            row_state = self._apply_auto_chain(row_state, "auto_chain_rows")
            self._save(col_state, row_state, cells)
            self._rebuild_rows()

        elif action == "remove_column":
            col_ref = body.get("column", "")
            col_key = self._resolve_column(col_ref)
            if not col_key:
                return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action=action)
            try:
                col_state = col_oc.remove(col_key)
            except ValueError as e:
                return self._error(str(e), action=action)
            for row_id in cells:
                cells[row_id].pop(col_key, None)
            col_state = self._apply_auto_chain(col_state, "auto_chain_cols")
            self._save(col_state, row_state, cells)

        elif action == "move_row_up":
            row_id = body.get("row", "")
            try:
                row_state = row_oc.move_up(row_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            row_state = self._apply_auto_chain(row_state, "auto_chain_rows")
            self._save(col_state, row_state, cells)

        elif action == "move_row_down":
            row_id = body.get("row", "")
            try:
                row_state = row_oc.move_down(row_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            row_state = self._apply_auto_chain(row_state, "auto_chain_rows")
            self._save(col_state, row_state, cells)

        elif action == "move_col_left":
            col_ref = body.get("column", "")
            col_key = self._resolve_column(col_ref)
            if not col_key:
                return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action=action)
            try:
                col_state = col_oc.move_up(col_key)
            except ValueError as e:
                return self._error(str(e), action=action)
            col_state = self._apply_auto_chain(col_state, "auto_chain_cols")
            self._save(col_state, row_state, cells)

        elif action == "move_col_right":
            col_ref = body.get("column", "")
            col_key = self._resolve_column(col_ref)
            if not col_key:
                return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action=action)
            try:
                col_state = col_oc.move_down(col_key)
            except ValueError as e:
                return self._error(str(e), action=action)
            col_state = self._apply_auto_chain(col_state, "auto_chain_cols")
            self._save(col_state, row_state, cells)

        elif action == "add_row_constraint":
            item_id = body.get("item", "")
            after_id = body.get("after", "")
            try:
                row_state = row_oc.add_constraint(item_id, after_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._save(col_state, row_state, cells)

        elif action == "remove_row_constraint":
            item_id = body.get("item", "")
            after_id = body.get("after", "")
            try:
                row_state = row_oc.remove_constraint(item_id, after_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._save(col_state, row_state, cells)

        elif action == "add_col_constraint":
            item_id = body.get("item", "")
            after_id = body.get("after", "")
            try:
                col_state = col_oc.add_constraint(item_id, after_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._save(col_state, row_state, cells)

        elif action == "remove_col_constraint":
            item_id = body.get("item", "")
            after_id = body.get("after", "")
            try:
                col_state = col_oc.remove_constraint(item_id, after_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._save(col_state, row_state, cells)

        elif action == "toggle_auto_chain_rows":
            config = dict(self._config)
            config["auto_chain_rows"] = not config.get("auto_chain_rows", False)
            if config["auto_chain_rows"]:
                row_state = self._apply_auto_chain(row_state, "auto_chain_rows", config)
            else:
                row_state.pop("constraints", None)
            self._save(col_state, row_state, cells, config=config)

        elif action == "toggle_auto_chain_cols":
            config = dict(self._config)
            config["auto_chain_cols"] = not config.get("auto_chain_cols", False)
            if config["auto_chain_cols"]:
                col_state = self._apply_auto_chain(col_state, "auto_chain_cols", config)
            else:
                col_state.pop("constraints", None)
            self._save(col_state, row_state, cells, config=config)

        else:
            return self._error(f"Unknown action: {action}", action=action)

        return self.serialize()
