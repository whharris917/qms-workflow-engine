"""TableForm action handlers — extracted from tableform.py.

Contains all _do_* action methods for TableForm's 17 registered actions.
Mixed into TableForm via TableFormActionsMixin.
"""

from __future__ import annotations


class TableFormActionsMixin:
    """Action handler implementations for TableForm."""

    def _do_add_column(self, body: dict) -> dict:
        col_oc = self._col_collection
        row_oc = self._row_collection
        col_state, row_state, cells = self._current_states()
        label = body.get("label", "").strip()
        if not label:
            return self._error("Column label is required.", action="add_column")
        try:
            col_state = col_oc.add(label)
        except ValueError as e:
            return self._error(str(e), action="add_column")
        if not row_state.get("items"):
            row_state = row_oc.add("")
        new_col_id = col_state["items"][-1]["id"]
        for row_id in [i["id"] for i in row_state.get("items", [])]:
            cells.setdefault(row_id, {})[new_col_id] = None
        col_state = self._apply_auto_chain(col_state, "auto_chain_cols")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_rename_column(self, body: dict) -> dict:
        col_oc = self._col_collection
        col_state, row_state, cells = self._current_states()
        col_ref = body.get("column", "")
        new_label = body.get("label", "").strip()
        col_key = self._resolve_column(col_ref)
        if not col_key:
            return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action="rename_column")
        if not new_label:
            return self._error("New label is required.", action="rename_column")
        try:
            col_state = col_oc.edit(col_key, new_label)
        except ValueError as e:
            return self._error(str(e), action="rename_column")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_add_row(self, body: dict) -> dict:
        row_oc = self._row_collection
        col_state, row_state, cells = self._current_states()
        templates = self._typed_column_templates
        try:
            row_state = row_oc.add("")
        except ValueError as e:
            return self._error(str(e), action="add_row")
        new_row_id = row_state["items"][-1]["id"]
        row = {}
        for col_item in col_state.get("items", []):
            col_key = col_item["id"]
            if col_key in templates:
                continue
            val = body.get(col_key)
            if val is None:
                val = body.get(col_item.get("value", ""))
            row[col_key] = val
        cells[new_row_id] = row
        row_state = self._apply_auto_chain(row_state, "auto_chain_rows")
        self._save(col_state, row_state, cells)
        self._rebuild_rows()
        return self.serialize()

    def _do_set_cell(self, body: dict) -> dict:
        col_state, row_state, cells = self._current_states()
        templates = self._typed_column_templates
        row_id = body.get("row", "")
        col_ref = body.get("column", "")
        value = body.get("value")
        if row_id not in cells and row_id not in {i["id"] for i in row_state.get("items", [])}:
            return self._error(f"Unknown row: {row_id}. Valid: {', '.join(i['id'] for i in row_state.get('items', []))}", action="set_cell")
        col_key = self._resolve_column(col_ref)
        if not col_key:
            return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action="set_cell")
        if col_key in templates:
            return self._error(
                f"Column '{col_key}' is a typed column ({templates[col_key].form}). "
                f"Use its cell URL instead: {self.url}/<row_id>/{col_key}",
                action="set_cell",
            )
        cells.setdefault(row_id, {})[col_key] = value
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_set_row(self, body: dict) -> dict:
        col_state, row_state, cells = self._current_states()
        templates = self._typed_column_templates
        row_id = body.get("row", "")
        row_ids = {i["id"] for i in row_state.get("items", [])}
        if row_id not in row_ids:
            return self._error(f"Unknown row: {row_id}. Valid: {', '.join(row_ids)}", action="set_row")
        for col_item in col_state.get("items", []):
            col_key = col_item["id"]
            if col_key in templates:
                continue
            val = body.get(col_key)
            if val is None:
                val = body.get(col_item.get("value", ""))
            if val is not None:
                cells.setdefault(row_id, {})[col_key] = val
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_remove_row(self, body: dict) -> dict:
        row_oc = self._row_collection
        col_state, row_state, cells = self._current_states()
        templates = self._typed_column_templates
        row_id = body.get("row", "")
        if templates and self._store:
            self._store.clear_scope(f"{self.key}/{row_id}")
        try:
            row_state = row_oc.remove(row_id)
        except ValueError as e:
            return self._error(str(e), action="remove_row")
        cells.pop(row_id, None)
        row_state = self._apply_auto_chain(row_state, "auto_chain_rows")
        self._save(col_state, row_state, cells)
        self._rebuild_rows()
        return self.serialize()

    def _do_remove_column(self, body: dict) -> dict:
        col_oc = self._col_collection
        col_state, row_state, cells = self._current_states()
        col_ref = body.get("column", "")
        col_key = self._resolve_column(col_ref)
        if not col_key:
            return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action="remove_column")
        try:
            col_state = col_oc.remove(col_key)
        except ValueError as e:
            return self._error(str(e), action="remove_column")
        for row_id in cells:
            cells[row_id].pop(col_key, None)
        col_state = self._apply_auto_chain(col_state, "auto_chain_cols")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_move_row_up(self, body: dict) -> dict:
        row_oc = self._row_collection
        col_state, row_state, cells = self._current_states()
        row_id = body.get("row", "")
        try:
            row_state = row_oc.move_up(row_id)
        except ValueError as e:
            return self._error(str(e), action="move_row_up")
        row_state = self._apply_auto_chain(row_state, "auto_chain_rows")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_move_row_down(self, body: dict) -> dict:
        row_oc = self._row_collection
        col_state, row_state, cells = self._current_states()
        row_id = body.get("row", "")
        try:
            row_state = row_oc.move_down(row_id)
        except ValueError as e:
            return self._error(str(e), action="move_row_down")
        row_state = self._apply_auto_chain(row_state, "auto_chain_rows")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_move_col_left(self, body: dict) -> dict:
        col_oc = self._col_collection
        col_state, row_state, cells = self._current_states()
        col_ref = body.get("column", "")
        col_key = self._resolve_column(col_ref)
        if not col_key:
            return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action="move_col_left")
        try:
            col_state = col_oc.move_up(col_key)
        except ValueError as e:
            return self._error(str(e), action="move_col_left")
        col_state = self._apply_auto_chain(col_state, "auto_chain_cols")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_move_col_right(self, body: dict) -> dict:
        col_oc = self._col_collection
        col_state, row_state, cells = self._current_states()
        col_ref = body.get("column", "")
        col_key = self._resolve_column(col_ref)
        if not col_key:
            return self._error(f"Unknown column: {col_ref}. Valid: {', '.join(self.col_keys)}", action="move_col_right")
        try:
            col_state = col_oc.move_down(col_key)
        except ValueError as e:
            return self._error(str(e), action="move_col_right")
        col_state = self._apply_auto_chain(col_state, "auto_chain_cols")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_add_row_constraint(self, body: dict) -> dict:
        row_oc = self._row_collection
        col_state, row_state, cells = self._current_states()
        item_id = body.get("item", "")
        after_id = body.get("after", "")
        try:
            row_state = row_oc.add_constraint(item_id, after_id)
        except ValueError as e:
            return self._error(str(e), action="add_row_constraint")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_remove_row_constraint(self, body: dict) -> dict:
        row_oc = self._row_collection
        col_state, row_state, cells = self._current_states()
        item_id = body.get("item", "")
        after_id = body.get("after", "")
        try:
            row_state = row_oc.remove_constraint(item_id, after_id)
        except ValueError as e:
            return self._error(str(e), action="remove_row_constraint")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_add_col_constraint(self, body: dict) -> dict:
        col_oc = self._col_collection
        col_state, row_state, cells = self._current_states()
        item_id = body.get("item", "")
        after_id = body.get("after", "")
        try:
            col_state = col_oc.add_constraint(item_id, after_id)
        except ValueError as e:
            return self._error(str(e), action="add_col_constraint")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_remove_col_constraint(self, body: dict) -> dict:
        col_oc = self._col_collection
        col_state, row_state, cells = self._current_states()
        item_id = body.get("item", "")
        after_id = body.get("after", "")
        try:
            col_state = col_oc.remove_constraint(item_id, after_id)
        except ValueError as e:
            return self._error(str(e), action="remove_col_constraint")
        self._save(col_state, row_state, cells)
        return self.serialize()

    def _do_toggle_auto_chain_rows(self, body: dict) -> dict:
        col_state, row_state, cells = self._current_states()
        config = dict(self._config)
        config["auto_chain_rows"] = not config.get("auto_chain_rows", False)
        if config["auto_chain_rows"]:
            row_state = self._apply_auto_chain(row_state, "auto_chain_rows", config)
        else:
            row_state.pop("constraints", None)
        self._save(col_state, row_state, cells, config=config)
        return self.serialize()

    def _do_toggle_auto_chain_cols(self, body: dict) -> dict:
        col_state, row_state, cells = self._current_states()
        config = dict(self._config)
        config["auto_chain_cols"] = not config.get("auto_chain_cols", False)
        if config["auto_chain_cols"]:
            col_state = self._apply_auto_chain(col_state, "auto_chain_cols", config)
        else:
            col_state.pop("constraints", None)
        self._save(col_state, row_state, cells, config=config)
        return self.serialize()
