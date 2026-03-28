"""TableForm — a tabular eigenform with columns, rows, and cell-level interaction.

A table is a self-contained HATEOAS-compliant application. Its state is a
2D grid of typed cells. Its affordances allow structural operations (add/remove
rows and columns) and data operations (set cell values, set entire rows). The
available affordances change based on state.

Rows have stable IDs (row_0, row_1, ...) that do not change when other rows
are removed. This prevents index-shifting bugs in concurrent or multi-step
operations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import (
    Affordance,
    SimpleButtonAffordance,
    STYLE_REMOVE,
    render_inline_button,
)
from engine.eigenforms import Eigenform
from engine.store import Store


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
    """A table with dynamic columns, stable row IDs, and row-level operations."""

    @property
    def _state(self) -> dict:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored
        return {"columns": [], "rows": {}, "row_order": [], "next_row_id": 0}

    @property
    def columns(self) -> list[dict]:
        """Column definitions: [{"key": "col_0", "label": "Name"}, ...]"""
        return self._state.get("columns", [])

    @property
    def col_keys(self) -> list[str]:
        return [c["key"] for c in self.columns]

    @property
    def col_labels(self) -> dict[str, str]:
        """Map of key -> label."""
        return {c["key"]: c["label"] for c in self.columns}

    @property
    def rows(self) -> dict[str, dict]:
        """Row data keyed by stable ID: {"row_0": {"col_0": "Alice", ...}, ...}"""
        return self._state.get("rows", {})

    @property
    def row_order(self) -> list[str]:
        """Ordered list of row IDs."""
        return self._state.get("row_order", [])

    @property
    def _next_row_id(self) -> int:
        return self._state.get("next_row_id", 0)

    @property
    def _next_col_id(self) -> int:
        return self._state.get("next_col_id", 0)

    @property
    def is_complete(self) -> bool:
        if not self.columns or not self.rows:
            return False
        for row_id in self.row_order:
            row = self.rows.get(row_id, {})
            for col in self.columns:
                if row.get(col["key"]) is None:
                    return False
        return True

    def _save(self, columns, rows, row_order, next_row_id=None, next_col_id=None):
        state = {
            "columns": columns,
            "rows": rows,
            "row_order": row_order,
            "next_row_id": next_row_id if next_row_id is not None else self._next_row_id,
            "next_col_id": next_col_id if next_col_id is not None else self._next_col_id,
        }
        self._store.set(self._scope, self.key, state)

    def _resolve_column(self, ref: str) -> str | None:
        """Resolve a column reference — accepts key or label."""
        for c in self.columns:
            if c["key"] == ref:
                return ref
        for c in self.columns:
            if c["label"] == ref:
                return c["key"]
        return None

    def _serialize_state(self) -> dict:
        ordered_rows = []
        for row_id in self.row_order:
            row_data = self.rows.get(row_id, {})
            ordered_rows.append({"_id": row_id, **row_data})
        return self._base_state() | {
            "columns": self.columns,
            "rows": ordered_rows,
            "summary": f"{len(self.columns)} {'column' if len(self.columns) == 1 else 'columns'}, {len(self.row_order)} {'row' if len(self.row_order) == 1 else 'rows'}",
        }

    def get_affordances(self) -> list[Affordance]:
        affordances: list[Affordance] = []
        col_keys = " | ".join(c["key"] for c in self.columns) if self.columns else ""
        row_ids = " | ".join(self.row_order) if self.row_order else ""

        # Add column
        affordances.append(AddColumnAffordance(
            label="+ Column",
            method="POST",
            url=self.url,
            body={"action": "add_column", "label": "<column name>"},
            instruction="Add a new column. Provide the column label.",
        ))

        # Rename column
        if self.columns:
            affordances.append(Affordance(
                label="Rename Column",
                method="POST",
                url=self.url,
                body={"action": "rename_column", "column": f"<{col_keys}>", "label": "<new label>"},
                instruction="Rename a column. Accepts column key or current label.",
            ))

        # Add row (with optional initial values)
        if self.columns:
            col_desc = ", ".join(f"{c['key']} ({c['label']})" for c in self.columns)
            affordances.append(Affordance(
                label="+ Row",
                method="POST",
                url=self.url,
                body={"action": "add_row"},
                instruction=f"Add a new row. Optionally include column keys with values: {col_desc}. Omitted columns default to empty.",
            ))

        # Set cell
        if self.columns and self.row_order:
            affordances.append(SetCellAffordance(
                label="Set Cell",
                method="POST",
                url=self.url,
                body={"action": "set_cell", "row": f"<{row_ids}>", "column": f"<{col_keys}>", "value": "<value>"},
                instruction="Set a cell value. Row is a row ID. Column is a key or label.",
            ))

        # Set row
        if self.columns and self.row_order:
            body = {"action": "set_row", "row": f"<{row_ids}>"}
            for c in self.columns:
                body[c["key"]] = f"<{c['label']} value>"
            affordances.append(Affordance(
                label="Set Row",
                method="POST",
                url=self.url,
                body=body,
                instruction="Set multiple cells in a row at once. Omitted columns are unchanged.",
            ))

        # Remove row
        if self.row_order:
            affordances.append(Affordance(
                label="Remove Row",
                method="POST",
                url=self.url,
                body={"action": "remove_row", "row": f"<{row_ids}>"},
                instruction="Remove a row by ID.",
            ))

        # Remove column
        if self.columns:
            affordances.append(Affordance(
                label="Remove Column",
                method="POST",
                url=self.url,
                body={"action": "remove_column", "column": f"<{col_keys}>"},
                instruction="Remove a column by key or label.",
            ))

        return affordances

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        columns = data.get("columns", [])
        rows = data.get("rows", [])
        affs = data.get("affordances", [])

        # Find the URL from any affordance
        url = affs[0]["url"] if affs else ""

        if columns:
            html += '<table style="border-collapse: collapse; margin: 8px 0;">'

            # Header — column labels are inline-editable
            html += '<tr>'
            html += '<th style="border: 1px solid #ccc; padding: 4px 8px; background: #f0f0f0;">ID</th>'
            for col in columns:
                rm_col_body = {"action": "remove_column", "column": col["key"]}
                rm_col_btn = render_inline_button(url, rm_col_body, "\u2212", STYLE_REMOVE)
                html += (
                    f'<th style="border: 1px solid #ccc; padding: 2px; background: #f0f0f0;">'
                    f'<form style="margin:0" onsubmit="fetch(\'{url}\','
                    f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                    f'body:JSON.stringify({{action:\'rename_column\',column:\'{col["key"]}\','
                    f'label:this.elements.v.value}})'
                    f'}}).then(()=>location.reload()); return false">'
                    f'<input name="v" type="text" value="{escape(col["label"])}"'
                    f' style="border: none; width: 100%; box-sizing: border-box; padding: 2px 4px;'
                    f' background: transparent; font-weight: bold; text-align: center;"'
                    f' oninput="this.title=\'POST {url} \'+JSON.stringify({{action:\'rename_column\',column:\'{col["key"]}\',label:this.value}})"'
                    f' title="POST {url} {escape(json.dumps({"action": "rename_column", "column": col["key"], "label": col["label"]}))}" />'
                    f'</form>'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; padding: 0 4px;">'
                    f'<span style="font-size: 10px; color: #888;">{escape(col["key"])}</span>'
                    f'{rm_col_btn}'
                    f'</div>'
                    f'</th>'
                )
            # +Column as last header cell — inline input
            add_col_aff = next((a for a in affs if a.get("body", {}).get("action") == "add_column"), None)
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

            # Rows — each cell is an inline form, with a remove button at the end
            for row_data in rows:
                row_id = row_data["_id"]
                rm_row_body = {"action": "remove_row", "row": row_id}
                rm_row_btn = render_inline_button(url, rm_row_body, "\u2212", STYLE_REMOVE)
                html += '<tr>'
                html += (
                    f'<td style="border: 1px solid #ccc; padding: 4px 8px; color: #888;'
                    f' font-size: 11px; white-space: nowrap;">'
                    f'{rm_row_btn}'
                    f' {escape(row_id)}'
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

            # +Row button as a final row, aligned with the "−" buttons
            add_row_aff = next((a for a in affs if a.get("body", {}).get("action") == "add_row"), None)
            if add_row_aff:
                add_row_body = json.dumps({"action": "add_row"})
                html += (
                    f'<tr>'
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
            # Empty table — show just the +Column input to get started
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
        from engine.eigenforms import Eigenform
        for aff in affs:
            hints_type = aff.get("render_hints", {}).get("type", "")
            action = aff.get("body", {}).get("action", "")
            if hints_type == "inline_cell" or action in ("rename_column", "remove_column", "remove_row", "add_row", "add_column"):
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
        columns = list(self.columns)
        rows = dict(self.rows)
        row_order = list(self.row_order)
        next_row_id = self._next_row_id
        next_col_id = self._next_col_id

        if action == "add_column":
            label = body.get("label", "").strip()
            if not label:
                return self._error("Column label is required.", action=action)
            key = f"col_{next_col_id}"
            next_col_id += 1
            columns.append({"key": key, "label": label})
            for row_id in row_order:
                rows[row_id][key] = None
            self._save(columns, rows, row_order, next_row_id, next_col_id)

        elif action == "rename_column":
            col_ref = body.get("column", "")
            new_label = body.get("label", "").strip()
            col_key = self._resolve_column(col_ref)
            if not col_key:
                return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action=action)
            if not new_label:
                return self._error("New label is required.", action=action)
            for c in columns:
                if c["key"] == col_key:
                    c["label"] = new_label
                    break
            self._save(columns, rows, row_order, next_row_id, next_col_id)

        elif action == "add_row":
            row_id = f"row_{next_row_id}"
            next_row_id += 1
            row = {}
            for col in columns:
                val = body.get(col["key"])
                if val is None:
                    val = body.get(col["label"])
                row[col["key"]] = val
            rows[row_id] = row
            row_order.append(row_id)
            self._save(columns, rows, row_order, next_row_id, next_col_id)

        elif action == "set_cell":
            row_id = body.get("row", "")
            col_ref = body.get("column", "")
            value = body.get("value")
            if row_id not in rows:
                return self._error(f"Unknown row: {row_id}. Valid: {', '.join(row_order)}", action=action)
            col_key = self._resolve_column(col_ref)
            if not col_key:
                return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action=action)
            rows[row_id][col_key] = value
            self._save(columns, rows, row_order, next_row_id, next_col_id)

        elif action == "set_row":
            row_id = body.get("row", "")
            if row_id not in rows:
                return self._error(f"Unknown row: {row_id}. Valid: {', '.join(row_order)}", action=action)
            for col in columns:
                val = body.get(col["key"])
                if val is None:
                    val = body.get(col["label"])
                if val is not None:
                    rows[row_id][col["key"]] = val
            self._save(columns, rows, row_order, next_row_id, next_col_id)

        elif action == "remove_row":
            row_id = body.get("row", "")
            if row_id not in rows:
                return self._error(f"Unknown row: {row_id}. Valid: {', '.join(row_order)}", action=action)
            del rows[row_id]
            row_order.remove(row_id)
            self._save(columns, rows, row_order, next_row_id, next_col_id)

        elif action == "remove_column":
            col_ref = body.get("column", "")
            col_key = self._resolve_column(col_ref)
            if not col_key:
                return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action=action)
            columns = [c for c in columns if c["key"] != col_key]
            for row_id in row_order:
                rows[row_id].pop(col_key, None)
            self._save(columns, rows, row_order, next_row_id, next_col_id)

        else:
            return self._error(f"Unknown action: {action}", action=action)

        return self.serialize()
