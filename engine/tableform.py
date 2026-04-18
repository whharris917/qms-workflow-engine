"""TableForm — a tabular component with columns, rows, and cell-level interaction.

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
    BUTTON_GAP, STYLE_CONFIRM, STYLE_REMOVE, STYLE_ARROW,
    CSS_CONFIRM, CSS_REMOVE, CSS_ARROW, render_inline_button,
)
from engine.component import Component
from engine.ordered_collection import OrderedCollection
from engine.tableform_actions import TableFormActionsMixin
from engine.templates import render_template


class SetCellAffordance(Affordance):
    """An affordance that sets a single cell value."""

    def _render_hints(self) -> dict:
        return {"type": "inline_cell"}


class AddColumnAffordance(Affordance):
    """An affordance that adds a column to the table."""

    def _render_hints(self) -> dict:
        return {"type": "text_input_add", "placeholder": "Column name"}


@dataclass
class RowGroup(Component):
    """Lightweight routing node for one row's typed cell components.

    Created by TableForm._bind_children(). Enables find_component to
    traverse table_key -> row_id -> col_id for path-based access to
    typed cell components.
    """
    cell_components: dict[str, Component] = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return False  # Parent TableForm handles clearing

    @property
    def children(self) -> list[Component]:
        return list(self.cell_components.values())

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.cell_components.values())

    def _serialize_state(self) -> dict:
        state = self._base_state()
        state["form"] = "row"
        return state

    def render_from_data(self, data: dict) -> str:
        return ""  # Never rendered standalone

    def get_affordances(self) -> list[Affordance]:
        return []


@dataclass
class TableForm(TableFormActionsMixin, Component):
    """A table with dynamic columns, stable row IDs, and row-level operations.

    Both rows and columns are backed by OrderedCollection, providing:
    - Stable IDs (row_0, col_0, ...)
    - Fixed items (immutable rows/columns)
    - Ordering constraints (must_follow)
    - Constraint-aware move up/down (rows) and left/right (columns)
    """
    form = "table"

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
        """Extract string labels from fixed_columns, handling both str and Component entries."""
        return [c.label if isinstance(c, Component) else c for c in self.fixed_columns]

    @property
    def _typed_column_templates(self) -> dict[str, Component]:
        """Map col_id -> unbound component template for typed columns."""
        return {
            f"col_{i}": c
            for i, c in enumerate(self.fixed_columns)
            if isinstance(c, Component)
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
        # Seed fixed rows on first access, including cell data
        if state is None and self.fixed_rows:
            items = [{"id": f"row_{i}", "value": "", "fixed": True}
                     for i in range(len(self.fixed_rows))]
            state = {"items": items, "next_id": len(self.fixed_rows)}
            if self._store is not None:
                cells = {f"row_{i}": dict(rd) for i, rd in enumerate(self.fixed_rows)}
                col_oc = self._col_collection
                col_state = {"items": [dict(i) for i in col_oc.items], "next_id": col_oc.next_id}
                self._store.set(self._scope, self.key, {
                    "columns": col_state,
                    "rows_meta": state,
                    "cells": cells,
                })
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
    def children(self) -> list[Component]:
        return list(getattr(self, '_row_groups', []))

    def _bind_children(self, store, url_prefix: str):
        """Create RowGroups with bound cell components for all typed columns."""
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
                cell_components=cells,
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
                        ef = rg.cell_components.get(col_id)
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
                    ef = rg.cell_components.get(col_id)
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
            f' opacity: 0; cursor: pointer;"'
            f' data-c-change="{escape(url)}"'
            f' data-c-template="{escape(json.dumps({"action": add_action, "item": item_id, "after": "__VALUE"}))}"'
            f'>'
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
                    "x", CSS_REMOVE,
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
        col_oc = self._col_collection
        row_oc = self._row_collection
        col_items = col_oc.items
        row_items = row_oc.items
        templates = self._typed_column_templates
        row_groups_by_id = {rg.key: rg for rg in getattr(self, '_row_groups', [])}

        columns = data.get("columns", [])
        rows = data.get("rows", [])
        affs = data.get("affordances", [])
        url = affs[0]["url"] if affs else ""
        gap = BUTTON_GAP
        num_rows = len(row_items)
        num_cols = len(col_items)

        # Config toggles
        config = self._config
        config_toggles = []
        if self.allow_row_constraints:
            config_toggles.append(("auto_chain_rows", "toggle_auto_chain_rows", "Auto-chain rows"))
        if self.allow_col_constraints:
            config_toggles.append(("auto_chain_cols", "toggle_auto_chain_cols", "Auto-chain columns"))

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

        add_col_aff = next((a for a in affs if a.get("body", {}).get("action") == "add_column"), None)
        add_row_aff = next((a for a in affs if a.get("body", {}).get("action") == "add_row"), None)

        # Build column headers
        col_headers = []
        for ci, col in enumerate(columns):
            col_item = col_items[ci] if ci < len(col_items) else None
            col_id = col["key"]
            is_fixed_col = col_item.get("fixed", False) if col_item else False

            left_arrow = gap
            right_arrow = gap
            if num_cols > 1:
                if col_oc.can_move_up(ci, col_items):
                    left_arrow = render_inline_button(url, {"action": "move_col_left", "column": col_id}, "&#9664;", CSS_ARROW)
                if col_oc.can_move_down(ci, col_items):
                    right_arrow = render_inline_button(url, {"action": "move_col_right", "column": col_id}, "&#9654;", CSS_ARROW)

            rm_col_btn = ''
            if not is_fixed_col:
                rm_col_btn = render_inline_button(url, {"action": "remove_column", "column": col_id}, "\u2212", CSS_REMOVE)

            constraint_html = ''
            if show_col_constraints:
                prereqs = col_mf.get(col_id, [])
                if prereqs or len(col_items) > 1:
                    constraint_html = (
                        f'<div style="display: flex; align-items: center; justify-content: center; padding: 2px 4px 0 4px; border-top: 1px solid #e0e0e0;">'
                        + self._render_constraint_inline(
                            url, col_id, prereqs, col_id_to_val, col_static_pairs,
                            col_items, "add_col_constraint", "remove_col_constraint",
                            "#e8e8f4")
                        + '</div>'
                    )

            col_pill = (
                f'<span style="display: inline-block; min-width: 52px; color: #666;'
                f' text-align: center; background: #e8e8e8; border-radius: 10px;'
                f' padding: 1px 6px; font-family: monospace; font-size: 0.85em;">'
                f'{escape(col_id)}</span>'
            )
            rm_or_gap = rm_col_btn if rm_col_btn else gap

            id_row_html = (
                f'<div style="display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; padding: 2px 4px;">'
                f'<div style="text-align: left;">{left_arrow}</div>'
                f'<div>{col_pill}</div>'
                f'<div style="text-align: right;">{right_arrow}</div>'
                f'</div>'
            )

            if is_fixed_col:
                rename_html = (
                    f'<div style="display: flex; align-items: center; padding: 2px 4px; gap: 4px;">'
                    f'{rm_or_gap}'
                    f'<span style="flex: 1; font-weight: bold; text-align: center; color: #555;">'
                    f'{escape(col["label"])}</span>'
                    f'{gap}'
                    f'</div>'
                )
            else:
                rename_body = {"action": "rename_column", "column": col_id, "label": col["label"]}
                rename_tooltip = f'POST {url} {escape(json.dumps(rename_body))}'
                rename_html = (
                    f'<div style="display: flex; align-items: center; padding: 2px 4px; gap: 4px;">'
                    f'{rm_or_gap}'
                    f'<form style="margin:0; flex: 1;" data-c-submit="{escape(url)}">'
                    f'<input type="hidden" name="action" value="rename_column" />'
                    f'<input type="hidden" name="column" value="{escape(col_id)}" />'
                    f'<input name="label" type="text" value="{escape(col["label"])}" size="12"'
                    f' style="border: 1px solid #ddd; padding: 2px 4px; width: 100%; box-sizing: border-box;'
                    f' font-family: inherit; font-size: inherit;'
                    f' font-weight: bold; text-align: center; color: #555;"'
                    f' title="{rename_tooltip}" />'
                    f'</form>'
                    f'<button style="{STYLE_CONFIRM}"'
                    f' title="{rename_tooltip}"'
                    f' onclick="this.closest(\'th\').querySelector(\'form\').requestSubmit(); return false;"'
                    f'>&#10003;</button>'
                    f'</div>'
                )

            col_headers.append({
                "col_id": col_id, "label": col["label"], "is_fixed": is_fixed_col,
                "id_row_html": id_row_html, "rename_html": rename_html,
                "rm_html": rm_col_btn, "constraint_html": constraint_html,
            })

        # Build add column HTML
        add_col_html = ""
        if add_col_aff:
            add_col_body_preview = json.dumps({"action": "add_column", "label": ""})
            add_col_tooltip = f'POST {url} {escape(add_col_body_preview)}'
            add_col_html = (
                f'<div style="padding: 2px 4px;">{gap}</div>'
                f'<div style="display: flex; align-items: center; padding: 2px 4px; gap: 4px;">'
                f'<form style="margin:0; flex: 1;" data-c-submit="{escape(url)}">'
                f'<input type="hidden" name="action" value="add_column" />'
                f'<input name="label" type="text" placeholder="Column name" size="12"'
                f' style="border: 1px solid #ddd; padding: 2px 4px; width: 100%; box-sizing: border-box;'
                f' font-family: inherit; font-size: inherit;'
                f' font-weight: bold; text-align: center; color: #555;"'
                f' title="{add_col_tooltip}" />'
                f'</form>'
                f'<button style="{STYLE_CONFIRM}"'
                f' title="{add_col_tooltip}"'
                f' onclick="this.closest(\'th\').querySelector(\'form\').requestSubmit(); return false;"'
                f'>+</button>'
                f'</div>'
            )

        # Build row data items
        row_data_items = []
        for ri, row_data in enumerate(rows):
            row_id = row_data["_id"]
            row_item = row_items[ri] if ri < len(row_items) else None
            is_fixed_row = row_item.get("fixed", False) if row_item else False

            rm_html = gap
            if not is_fixed_row:
                rm_html = render_inline_button(url, {"action": "remove_row", "row": row_id}, "\u2212", CSS_REMOVE)

            up_html = gap
            down_html = gap
            if num_rows > 1:
                if row_oc.can_move_up(ri, row_items):
                    up_html = render_inline_button(url, {"action": "move_row_up", "row": row_id}, "&#9650;", CSS_ARROW)
                if row_oc.can_move_down(ri, row_items):
                    down_html = render_inline_button(url, {"action": "move_row_down", "row": row_id}, "&#9660;", CSS_ARROW)

            prereq_dropdown_html = ""
            if show_row_constraints:
                prereqs = row_mf.get(row_id, [])
                prereq_dropdown_html = self._render_constraint_dropdown(
                    url, row_id, prereqs, row_items, "add_row_constraint")

            id_pill_html = (
                f'<span style="display: inline-block; min-width: 52px; color: #666;'
                f' text-align: center; background: #e8e8e8; border-radius: 10px;'
                f' padding: 1px 6px; font-family: monospace; font-size: 0.85em;">'
                f'{escape(row_id)}</span>'
            )

            prereq_pills_html = ""
            if any_row_prereqs:
                prereqs = row_mf.get(row_id, [])
                prereq_pills_html = self._render_constraint_pills(
                    url, row_id, prereqs, row_id_to_val, row_static_pairs,
                    "remove_row_constraint", "#e8f4e8")

            cells = []
            rg = row_groups_by_id.get(row_id)
            for col in columns:
                col_id = col["key"]
                if col_id in templates and rg:
                    ef = rg.cell_components.get(col_id)
                    if ef:
                        cells.append({"html": f'<td style="border: 1px solid #ccc; padding: 4px; vertical-align: top;">{ef.render_safely()}</td>'})
                    else:
                        cells.append({"html": '<td style="border: 1px solid #ccc; padding: 2px;"></td>'})
                else:
                    cell_value = row_data.get(col_id)
                    display = escape(str(cell_value)) if cell_value is not None else ""
                    cell_val_escaped = escape(str(cell_value)) if cell_value is not None else ""
                    cell_tooltip = f'POST {url} {escape(json.dumps({"action": "set_cell", "row": row_id, "column": col_id, "value": str(cell_val_escaped)}))}'
                    cells.append({"html": (
                        f'<td style="border: 1px solid #ccc; padding: 2px;">'
                        f'<form style="margin:0" data-c-submit="{escape(url)}">'
                        f'<input type="hidden" name="action" value="set_cell" />'
                        f'<input type="hidden" name="row" value="{escape(row_id)}" />'
                        f'<input type="hidden" name="column" value="{escape(col_id)}" />'
                        f'<input name="value" type="text" value="{display}"'
                        f' style="border: none; width: 100%; box-sizing: border-box; padding: 2px 4px;"'
                        f' title="{cell_tooltip}" />'
                        f'</form>'
                        f'</td>'
                    )})

            row_data_items.append({
                "row_id": row_id, "is_fixed": is_fixed_row,
                "rm_html": rm_html, "up_html": up_html, "down_html": down_html,
                "prereq_dropdown_html": prereq_dropdown_html,
                "id_pill_html": id_pill_html, "prereq_pills_html": prereq_pills_html,
                "cells": cells,
            })

        # Build add row HTML
        add_row_html = ""
        if add_row_aff and columns:
            add_row_body = json.dumps({"action": "add_row"})
            empty_td = '<td style="border: 1px solid #ccc; background: #f0f0f0;"></td>'
            add_row_html = (
                f'<tr>'
                f'<td style="border: 1px solid #ccc; padding: 2px 4px; text-align: center; background: #f0f0f0;">'
                f'<button data-c-post="{escape(url)}" data-c-body="{escape(add_row_body)}"'
                f' style="{STYLE_CONFIRM}"'
                f' title="POST {url} {escape(add_row_body)}">+</button>'
                f'</td>'
                + (empty_td * 2 if num_rows > 1 else '')
                + (empty_td if show_row_constraints else '')
                + empty_td
                + (empty_td if any_row_prereqs else '')
                + empty_td * len(columns)
                + (empty_td if add_col_aff else '')
                + '</tr>'
            )

        # Build empty-table column add HTML
        empty_col_html = ""
        if not columns and add_col_aff:
            add_col_body_preview = json.dumps({"action": "add_column", "label": ""})
            empty_col_html = (
                f'<table style="border-collapse: collapse; margin: 8px 0;">'
                f'<tr>'
                f'<th style="border: 1px solid #ccc; padding: 2px; background: #f0f0f0;">'
                f'<form style="margin:0; display: flex; align-items: center;"'
                f' data-c-submit="{escape(url)}">'
                f'<input type="hidden" name="action" value="add_column" />'
                f'<input name="label" type="text" placeholder="Column name" size="12"'
                f' style="border: 1px solid #ddd; width: 100px; padding: 2px 4px;"'
                f' title="POST {url} {escape(add_col_body_preview)}" />'
                f' <button type="submit" style="cursor: pointer; border: none; background: none; color: #2a2;'
                f' font-size: 14px; font-weight: bold; padding: 0 4px; line-height: 1;"'
                f' title="POST {url} {escape(add_col_body_preview)}">+</button>'
                f'</form>'
                f'</th>'
                f'</tr>'
                f'</table></div>'
            )

        return render_template("table.html", data=data, ef=self, url=url,
                               columns=columns, rows=rows,
                               config_toggles=config_toggles, config=config,
                               col_headers=col_headers,
                               row_data_items=row_data_items,
                               add_col_html=add_col_html,
                               add_row_html=add_row_html,
                               has_columns=bool(columns),
                               has_rows=bool(rows),
                               num_rows=num_rows,
                               num_cols=num_cols,
                               show_row_constraints=show_row_constraints,
                               show_col_constraints=show_col_constraints,
                               any_row_prereqs=any_row_prereqs,
                               empty_col_html=empty_col_html,
                               # Raw data for themed templates
                               col_oc=col_oc, row_oc=row_oc,
                               col_items=col_items, row_items=row_items,
                               typed_templates=templates,
                               row_groups_by_id=row_groups_by_id,
                               row_mf=row_mf, col_mf=col_mf,
                               row_id_to_val=row_id_to_val,
                               col_id_to_val=col_id_to_val,
                               row_static_pairs=row_static_pairs,
                               col_static_pairs=col_static_pairs)

    _actions = {
        "add_column": "_do_add_column",
        "rename_column": "_do_rename_column",
        "add_row": "_do_add_row",
        "set_cell": "_do_set_cell",
        "set_row": "_do_set_row",
        "remove_row": "_do_remove_row",
        "remove_column": "_do_remove_column",
        "move_row_up": "_do_move_row_up",
        "move_row_down": "_do_move_row_down",
        "move_col_left": "_do_move_col_left",
        "move_col_right": "_do_move_col_right",
        "add_row_constraint": "_do_add_row_constraint",
        "remove_row_constraint": "_do_remove_row_constraint",
        "add_col_constraint": "_do_add_col_constraint",
        "remove_col_constraint": "_do_remove_col_constraint",
        "toggle_auto_chain_rows": "_do_toggle_auto_chain_rows",
        "toggle_auto_chain_cols": "_do_toggle_auto_chain_cols",
    }

    # Action handler methods (_do_add_column, _do_add_row, _do_set_cell, etc.)
    # are provided by TableFormActionsMixin in engine/tableform_actions.py.
