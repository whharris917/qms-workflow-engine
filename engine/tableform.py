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

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import (
    Affordance, AddConstraintAffordance, SimpleButtonAffordance,
    BUTTON_GAP, STYLE_REMOVE, STYLE_ARROW, render_inline_button,
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
    def _col_collection(self) -> OrderedCollection:
        oc = OrderedCollection(
            id_prefix="col",
            fixed_items=self.fixed_columns,
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
        oc.load(state)
        return oc

    @property
    def _cells(self) -> dict[str, dict]:
        """Cell data: {"row_0": {"col_0": "Alice", ...}, ...}"""
        return self._raw_state.get("cells", {})

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

    @property
    def is_complete(self) -> bool:
        cols = self._col_collection.items
        rows_meta = self._row_collection.items
        cells = self._cells
        if not cols or not rows_meta:
            return False
        for row_item in rows_meta:
            row = cells.get(row_item["id"], {})
            for col_item in cols:
                if row.get(col_item["id"]) is None:
                    return False
        return True

    def _save(self, col_state: dict, row_state: dict, cells: dict):
        state = {
            "columns": col_state,
            "rows_meta": row_state,
            "cells": cells,
        }
        self._store.set(self._scope, self.key, state)

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
        ordered_rows = []
        for row_item in row_oc.items:
            row_data = cells.get(row_item["id"], {})
            ordered_rows.append({"_id": row_item["id"], **row_data})
        return self._base_state() | {
            "columns": self.columns,
            "rows": ordered_rows,
            "summary": f"{len(col_oc.items)} {'column' if len(col_oc.items) == 1 else 'columns'}, {len(row_oc.items)} {'row' if len(row_oc.items) == 1 else 'rows'}",
        }

    def get_affordances(self) -> list[Affordance]:
        affordances: list[Affordance] = []
        col_oc = self._col_collection
        row_oc = self._row_collection
        col_items = col_oc.items
        row_items = row_oc.items
        col_keys_str = " | ".join(i["id"] for i in col_items) if col_items else ""
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

        # Add row (with optional initial values)
        if col_items:
            col_desc = ", ".join(f"{i['id']} ({i['value']})" for i in col_items)
            affordances.append(Affordance(
                label="+ Row",
                method="POST",
                url=self.url,
                body={"action": "add_row"},
                instruction=f"Add a new row. Optionally include column keys with values: {col_desc}. Omitted columns default to empty.",
            ))

        # Set cell
        if col_items and row_items:
            affordances.append(SetCellAffordance(
                label="Set Cell",
                method="POST",
                url=self.url,
                body={"action": "set_cell", "row": f"<{row_ids_str}>", "column": f"<{col_keys_str}>", "value": "<value>"},
                instruction="Set a cell value. Row is a row ID. Column is a key or label.",
            ))

        # Set row
        if col_items and row_items:
            body: dict[str, Any] = {"action": "set_row", "row": f"<{row_ids_str}>"}
            for item in col_items:
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

        return affordances

    @staticmethod
    def _render_constraint_inline(
        url: str, item_id: str, prereqs: list[str],
        id_to_val: dict[str, str], static_pairs: set[tuple[str, str]],
        all_items: list[dict], add_action: str, remove_action: str,
        pill_bg: str, font_size: str,
    ) -> str:
        """Render inline constraint dropdown + prerequisite pills."""
        html = '<span style="display: inline-flex; align-items: center; gap: 2px; flex-wrap: wrap;">'
        available = [i for i in all_items if i["id"] != item_id and i["id"] not in prereqs]
        if available:
            add_opts = "".join(
                f'<option value="{escape(i["id"])}">'
                f'{escape(i["value"] or i["id"])} ({escape(i["id"])})</option>'
                for i in available
            )
            html += (
                f'<select style="width: 90px; font-size: {font_size};" onchange="'
                f"if(this.value)fetch('{url}',"
                f"{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                f"body:JSON.stringify({{action:'{add_action}',item:'{item_id}',after:this.value}})"
                f"}}).then(()=>location.reload())"
                f'">'
                f'<option value="">+ prereq</option>'
                f'{add_opts}'
                f'</select>'
            )
        if prereqs:
            html += f'<span style="font-style: italic; font-size: {font_size}; color: #999;">after</span>'
            for p_id in prereqs:
                p_name = escape(id_to_val.get(p_id, p_id))
                is_static = (item_id, p_id) in static_pairs
                html += (
                    f'<span style="background: {pill_bg}; padding: 0 4px;'
                    f' border-radius: 2px; font-size: {font_size};">{p_name}</span>'
                )
                if not is_static:
                    html += render_inline_button(
                        url, {"action": remove_action, "item": item_id, "after": p_id},
                        "x", STYLE_REMOVE,
                    )
        html += '</span>'
        return html

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        col_oc = self._col_collection
        row_oc = self._row_collection
        col_items = col_oc.items
        row_items = row_oc.items

        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        columns = data.get("columns", [])
        rows = data.get("rows", [])
        affs = data.get("affordances", [])

        url = affs[0]["url"] if affs else ""
        gap = BUTTON_GAP
        num_rows = len(row_items)
        num_cols = len(col_items)

        # Constraint display data
        show_row_constraints = self.allow_row_constraints and num_rows > 1
        show_col_constraints = self.allow_col_constraints and num_cols > 1
        row_mf = row_oc.effective_must_follow if show_row_constraints else {}
        col_mf = col_oc.effective_must_follow if show_col_constraints else {}
        row_id_to_val = row_oc.id_to_value
        col_id_to_val = col_oc.id_to_value
        row_static_pairs = {(iid, aid)
                            for iid, aids in self.row_must_follow.items()
                            for aid in aids} if show_row_constraints else set()
        col_static_pairs = {(iid, aid)
                            for iid, aids in self.col_must_follow.items()
                            for aid in aids} if show_col_constraints else set()

        if columns:
            add_col_aff = next((a for a in affs if a.get("body", {}).get("action") == "add_column"), None)
            add_row_aff = next((a for a in affs if a.get("body", {}).get("action") == "add_row"), None)

            # Row controls live in a borderless first column — structurally
            # inside the <tr> (guaranteeing alignment), visually outside the
            # data grid (no border, no background).
            ctrl_style = 'border: none; padding: 2px 4px 2px 0; white-space: nowrap;'

            html += '<table style="border-collapse: collapse; margin: 8px 0;">'

            # Header row — empty control cell + ID + data columns
            html += '<tr>'
            html += f'<th style="{ctrl_style}"></th>'
            html += '<th style="border: 1px solid #ccc; padding: 4px 8px; background: #f0f0f0;">ID</th>'

            for ci, col in enumerate(columns):
                col_item = col_items[ci] if ci < len(col_items) else None
                col_id = col["key"]
                is_fixed_col = col_item.get("fixed", False) if col_item else False

                # Column move buttons + remove button
                move_btns = ''
                if num_cols > 1:
                    if col_oc.can_move_up(ci, col_items):
                        move_btns += render_inline_button(url, {"action": "move_col_left", "column": col_id}, "&#9664;", STYLE_ARROW)
                    else:
                        move_btns += gap
                    if col_oc.can_move_down(ci, col_items):
                        move_btns += render_inline_button(url, {"action": "move_col_right", "column": col_id}, "&#9654;", STYLE_ARROW)
                    else:
                        move_btns += gap

                rm_col_btn = ''
                if not is_fixed_col:
                    rm_col_btn = render_inline_button(url, {"action": "remove_column", "column": col_id}, "\u2212", STYLE_REMOVE)

                # Column constraint row (if enabled)
                constraint_row = ''
                if show_col_constraints:
                    prereqs = col_mf.get(col_id, [])
                    if prereqs or len(col_items) > 1:
                        constraint_row = (
                            f'<div style="padding: 2px 4px; border-top: 1px solid #e0e0e0;">'
                            + self._render_constraint_inline(
                                url, col_id, prereqs, col_id_to_val, col_static_pairs,
                                col_items, "add_col_constraint", "remove_col_constraint",
                                "#e8e8f4", "10px")
                            + '</div>'
                        )

                if is_fixed_col:
                    html += (
                        f'<th style="border: 1px solid #ccc; padding: 2px; background: #f0f0f0;">'
                        f'<div style="padding: 2px 4px; font-weight: bold; text-align: center; color: #555;">'
                        f'{escape(col["label"])}</div>'
                        f'<div style="display: flex; justify-content: space-between; align-items: center; padding: 0 4px;">'
                        f'<span style="font-size: 10px; color: #888;">{escape(col_id)}</span>'
                        f'{move_btns}'
                        f'</div>'
                        f'{constraint_row}'
                        f'</th>'
                    )
                else:
                    html += (
                        f'<th style="border: 1px solid #ccc; padding: 2px; background: #f0f0f0;">'
                        f'<form style="margin:0" onsubmit="fetch(\'{url}\','
                        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                        f'body:JSON.stringify({{action:\'rename_column\',column:\'{col_id}\','
                        f'label:this.elements.v.value}})'
                        f'}}).then(()=>location.reload()); return false">'
                        f'<input name="v" type="text" value="{escape(col["label"])}"'
                        f' style="border: none; width: 100%; box-sizing: border-box; padding: 2px 4px;'
                        f' background: transparent; font-weight: bold; text-align: center;"'
                        f' oninput="this.title=\'POST {url} \'+JSON.stringify({{action:\'rename_column\',column:\'{col_id}\',label:this.value}})"'
                        f' title="POST {url} {escape(json.dumps({"action": "rename_column", "column": col_id, "label": col["label"]}))}" />'
                        f'</form>'
                        f'<div style="display: flex; justify-content: space-between; align-items: center; padding: 0 4px;">'
                        f'<span style="font-size: 10px; color: #888;">{escape(col_id)}</span>'
                        f'{move_btns}{rm_col_btn}'
                        f'</div>'
                        f'{constraint_row}'
                        f'</th>'
                    )

            # +Column as last header cell
            if add_col_aff:
                add_col_body_preview = json.dumps({"action": "add_column", "label": ""})
                html += (
                    f'<th style="border: 1px solid #ccc; padding: 2px; background: #f0f0f0; vertical-align: middle;">'
                    f'<form style="margin:0" onsubmit="fetch(\'{url}\','
                    f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                    f'body:JSON.stringify({{action:\'add_column\',label:this.elements.v.value}})'
                    f'}}).then(()=>location.reload()); return false">'
                    f'<input name="v" type="text" placeholder="+"'
                    f' style="border: none; width: 60px; box-sizing: border-box; padding: 2px 4px;'
                    f' background: transparent; text-align: center; color: #2a2; font-weight: bold;"'
                    f' oninput="this.title=\'POST {url} \'+JSON.stringify({{action:\'add_column\',label:this.value}})"'
                    f' title="POST {url} {escape(add_col_body_preview)}" />'
                    f'</form>'
                    f'</th>'
                )
            html += '</tr>'

            # Data rows — control cell + ID cell + data cells
            for ri, row_data in enumerate(rows):
                row_id = row_data["_id"]
                row_item = row_items[ri] if ri < len(row_items) else None
                is_fixed_row = row_item.get("fixed", False) if row_item else False

                html += '<tr>'

                # Control cell (borderless, outside the visual grid)
                html += f'<td style="{ctrl_style}">'
                if not is_fixed_row:
                    rm_row_body = {"action": "remove_row", "row": row_id}
                    html += render_inline_button(url, rm_row_body, "\u2212", STYLE_REMOVE)
                else:
                    html += gap
                if num_rows > 1:
                    if row_oc.can_move_up(ri, row_items):
                        html += render_inline_button(url, {"action": "move_row_up", "row": row_id}, "&#9650;", STYLE_ARROW)
                    else:
                        html += gap
                    if row_oc.can_move_down(ri, row_items):
                        html += render_inline_button(url, {"action": "move_row_down", "row": row_id}, "&#9660;", STYLE_ARROW)
                    else:
                        html += gap
                # Row constraint controls (inline in control cell)
                if show_row_constraints:
                    prereqs = row_mf.get(row_id, [])
                    if prereqs or num_rows > 1:
                        html += self._render_constraint_inline(
                            url, row_id, prereqs, row_id_to_val, row_static_pairs,
                            row_items, "add_row_constraint", "remove_row_constraint",
                            "#e8f4e8", "11px")
                html += '</td>'

                # ID cell
                html += (
                    f'<td style="border: 1px solid #ccc; padding: 4px 8px; color: #888;'
                    f' font-size: 11px; white-space: nowrap;">'
                    f'{escape(row_id)}'
                    f'</td>'
                )

                for col in columns:
                    cell_value = row_data.get(col["key"])
                    display = escape(str(cell_value)) if cell_value is not None else ""
                    cell_val_escaped = escape(str(cell_value)) if cell_value is not None else ""

                    html += (
                        f'<td style="border: 1px solid #ccc; padding: 2px;">'
                        f'<form style="margin:0" onsubmit="fetch(\'{url}\','
                        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                        f'body:JSON.stringify({{action:\'set_cell\',row:\'{row_id}\','
                        f'column:\'{col["key"]}\',value:this.elements.v.value}})'
                        f'}}).then(()=>location.reload()); return false">'
                        f'<input name="v" type="text" value="{display}"'
                        f' style="border: none; width: 100%; box-sizing: border-box; padding: 2px 4px;"'
                        f' oninput="this.title=\'POST {url} \'+JSON.stringify({{action:\'set_cell\',row:\'{row_id}\',column:\'{col["key"]}\',value:this.value}})"'
                        f' title="POST {url} {escape(json.dumps({"action": "set_cell", "row": row_id, "column": col["key"], "value": cell_val_escaped}))}" />'
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
                    f'<td style="{ctrl_style}"></td>'
                    f'<td style="border: 1px solid #ccc; padding: 4px 8px;">'
                    f'<button onclick="fetch(\'{url}\','
                    f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                    f'body:JSON.stringify({add_row_body.replace(chr(34), "&quot;")})}}).then(()=>location.reload())"'
                    f' style="cursor: pointer; border: none; background: none; color: #2a2;'
                    f' font-size: 14px; font-weight: bold; padding: 0 2px; line-height: 1;"'
                    f' title="POST {url} {escape(add_row_body)}">+</button>'
                    f'</td>'
                )
                for _ in columns:
                    html += '<td style="border: 1px solid #ccc;"></td>'
                if add_col_aff:
                    html += '<td style="border: 1px solid #ccc;"></td>'
                html += '</tr>'

            html += '</table>'
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
                    f'<input name="v" type="text" placeholder="Column name"'
                    f' style="border: 1px solid #ddd; width: 100px; padding: 2px 4px;"'
                    f' oninput="this.title=\'POST {url} \'+JSON.stringify({{action:\'add_column\',label:this.value}})"'
                    f' title="POST {url} {escape(add_col_body_preview)}" />'
                    f' <button type="submit" style="cursor: pointer; border: none; background: none; color: #2a2;'
                    f' font-size: 14px; font-weight: bold; padding: 0 4px; line-height: 1;"'
                    f' title="POST {url} {escape(add_col_body_preview)}">+</button>'
                    f'</form>'
                    f'</th>'
                    f'</tr>'
                    f'</table>'
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
                "set_row",
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

        if action == "add_column":
            label = body.get("label", "").strip()
            if not label:
                return self._error("Column label is required.", action=action)
            try:
                col_state = col_oc.add(label)
            except ValueError as e:
                return self._error(str(e), action=action)
            # Initialize cells for new column
            new_col_id = col_state["items"][-1]["id"]
            for row_id in [i["id"] for i in row_state.get("items", [])]:
                cells.setdefault(row_id, {})[new_col_id] = None
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
                val = body.get(col_key)
                if val is None:
                    val = body.get(col_item.get("value", ""))
                row[col_key] = val
            cells[new_row_id] = row
            self._save(col_state, row_state, cells)

        elif action == "set_cell":
            row_id = body.get("row", "")
            col_ref = body.get("column", "")
            value = body.get("value")
            if row_id not in cells and row_id not in {i["id"] for i in row_state.get("items", [])}:
                return self._error(f"Unknown row: {row_id}. Valid: {', '.join(i['id'] for i in row_state.get('items', []))}", action=action)
            col_key = self._resolve_column(col_ref)
            if not col_key:
                return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action=action)
            cells.setdefault(row_id, {})[col_key] = value
            self._save(col_state, row_state, cells)

        elif action == "set_row":
            row_id = body.get("row", "")
            row_ids = {i["id"] for i in row_state.get("items", [])}
            if row_id not in row_ids:
                return self._error(f"Unknown row: {row_id}. Valid: {', '.join(row_ids)}", action=action)
            for col_item in col_state.get("items", []):
                col_key = col_item["id"]
                val = body.get(col_key)
                if val is None:
                    val = body.get(col_item.get("value", ""))
                if val is not None:
                    cells.setdefault(row_id, {})[col_key] = val
            self._save(col_state, row_state, cells)

        elif action == "remove_row":
            row_id = body.get("row", "")
            try:
                row_state = row_oc.remove(row_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            cells.pop(row_id, None)
            self._save(col_state, row_state, cells)

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
            self._save(col_state, row_state, cells)

        elif action == "move_row_up":
            row_id = body.get("row", "")
            try:
                row_state = row_oc.move_up(row_id)
            except ValueError as e:
                return self._error(str(e), action=action)
            self._save(col_state, row_state, cells)

        elif action == "move_row_down":
            row_id = body.get("row", "")
            try:
                row_state = row_oc.move_down(row_id)
            except ValueError as e:
                return self._error(str(e), action=action)
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

        else:
            return self._error(f"Unknown action: {action}", action=action)

        return self.serialize()
