"""TableFormX — TableForm reimagined with native HTMX rendering.

Experimental copy of TableForm that replaces the affordance-based
rendering pipeline with direct HTMX attributes in the template. The
handler logic is identical — only the rendering path differs.

Two templates:
  - tablex.html       — agent view: naked semantic HTMX, no styling
  - tablex_human.html — human view: styled layout, same HTMX interactions
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.tableform import TableForm
from engine.templates import render_template


@dataclass
class TableFormX(TableForm):
    """HTMX-native TableForm. Same handler logic, HTMX-native rendering."""
    htmx_native = True

    def _template_context(self, data: dict) -> dict:
        """Shared context for both human and agent templates."""
        col_oc = self._col_collection
        row_oc = self._row_collection
        col_items = col_oc.items
        row_items = row_oc.items
        templates = self._typed_column_templates
        row_groups_by_id = {rg.key: rg for rg in getattr(self, '_row_groups', [])}
        cells = self._cells
        config = self._config

        # Constraint data
        show_row_constraints = self.allow_row_constraints and len(row_items) > 0
        show_col_constraints = self.allow_col_constraints and len(col_items) > 1
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
        any_row_prereqs = any(row_mf.get(i["id"]) for i in row_items) if show_row_constraints else False

        # Config toggles
        config_toggles = []
        if self.allow_row_constraints:
            config_toggles.append(("auto_chain_rows", "toggle_auto_chain_rows", "Auto-chain rows"))
        if self.allow_col_constraints:
            config_toggles.append(("auto_chain_cols", "toggle_auto_chain_cols", "Auto-chain columns"))

        # Build cell data for templates: list of rows, each with list of cell dicts
        row_data = []
        for ri, row_item in enumerate(row_items):
            row_id = row_item["id"]
            is_fixed = row_item.get("fixed", False)
            row_cells = cells.get(row_id, {})
            rg = row_groups_by_id.get(row_id)

            cell_list = []
            for col_item in col_items:
                col_id = col_item["id"]
                if col_id in templates and rg:
                    ef = rg.cell_eigenforms.get(col_id)
                    cell_list.append({
                        "col_id": col_id,
                        "typed": True,
                        "ef": ef,
                        "rendered": ef.render() if ef else "",
                    })
                else:
                    val = row_cells.get(col_id)
                    cell_list.append({
                        "col_id": col_id,
                        "typed": False,
                        "value": str(val) if val is not None else "",
                    })

            row_data.append({
                "id": row_id,
                "index": ri,
                "fixed": is_fixed,
                "can_up": row_oc.can_move_up(ri, row_items),
                "can_down": row_oc.can_move_down(ri, row_items),
                "prereqs": row_mf.get(row_id, []),
                "cells": cell_list,
            })

        # Column data for templates
        col_data = []
        for ci, col_item in enumerate(col_items):
            col_id = col_item["id"]
            is_fixed = col_item.get("fixed", False)
            is_typed = col_id in templates
            col_data.append({
                "id": col_id,
                "label": col_item["value"],
                "index": ci,
                "fixed": is_fixed,
                "typed": is_typed,
                "can_left": col_oc.can_move_up(ci, col_items),
                "can_right": col_oc.can_move_down(ci, col_items),
                "prereqs": col_mf.get(col_id, []),
            })

        # Parameterized affordance data (for agent template)
        all_row_ids = [i["id"] for i in row_items]
        all_col_ids = [i["id"] for i in col_items]
        text_col_items = [i for i in col_items if i["id"] not in templates]
        editable_cols = [i for i in col_items if not i.get("fixed")]
        editable_rows = [i for i in row_items if not i.get("fixed")]
        can_move_up_rows = [row_items[i]["id"] for i in range(len(row_items))
                            if row_oc.can_move_up(i, row_items)]
        can_move_down_rows = [row_items[i]["id"] for i in range(len(row_items))
                              if row_oc.can_move_down(i, row_items)]
        can_move_left_cols = [col_items[i]["id"] for i in range(len(col_items))
                              if col_oc.can_move_up(i, col_items)]
        can_move_right_cols = [col_items[i]["id"] for i in range(len(col_items))
                               if col_oc.can_move_down(i, col_items)]
        row_dynamic_constraints = row_oc.stored_constraints
        col_dynamic_constraints = col_oc.stored_constraints

        return dict(
            data=data,
            ef=self,
            url=self.url,
            label=data["label"],
            instruction=data.get("instruction") or "",
            col_items=col_items,
            row_items=row_items,
            col_data=col_data,
            row_data=row_data,
            num_rows=len(row_items),
            num_cols=len(col_items),
            has_data=self.has_data,
            config=config,
            config_toggles=config_toggles,
            show_row_constraints=show_row_constraints,
            show_col_constraints=show_col_constraints,
            any_row_prereqs=any_row_prereqs,
            row_mf=row_mf,
            col_mf=col_mf,
            row_id_to_val=row_id_to_val,
            col_id_to_val=col_id_to_val,
            row_static_pairs=row_static_pairs,
            col_static_pairs=col_static_pairs,
            # Parameterized affordance data
            all_row_ids=all_row_ids,
            all_col_ids=all_col_ids,
            text_col_items=text_col_items,
            editable_cols=editable_cols,
            editable_rows=editable_rows,
            can_move_up_rows=can_move_up_rows,
            can_move_down_rows=can_move_down_rows,
            can_move_left_cols=can_move_left_cols,
            can_move_right_cols=can_move_right_cols,
            row_dynamic_constraints=row_dynamic_constraints,
            col_dynamic_constraints=col_dynamic_constraints,
            typed_templates=templates,
        )

    def render_from_data(self, data: dict) -> str:
        return render_template("tablex_human.html", **self._template_context(data))

    def render_agent_from_data(self, data: dict) -> str:
        return render_template("tablex.html", **self._template_context(data))
