"""Affordance generation via recursive delegation.

Each workflow primitive implements get_affordances() and answers
"What is possible?" for itself. The node collects from all sources
and assigns sequential IDs. Adding a new primitive means adding a
new source class — the collection logic never changes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from .schema import (
    WorkflowDef, NodeDef, FieldDef, ListDef, NavigationDef,
    ProceedDef, ForkDef, ActionDef, TableDef,
)
from .evaluator import evaluate, check_visibility

from ..utils import trunc
from ..execution import PlanEngine
from ..execution.types import ColumnDef, PlanDefinition, ExecutionState, is_choice_list


# ---------------------------------------------------------------------------
# Context & Protocol
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AffordanceContext:
    """Immutable context passed through the affordance tree."""
    data: dict
    defn: WorkflowDef
    api_base: str            # e.g. "/agent/create-cr"


class AffordanceSource(Protocol):
    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        """Return affordances available right now. Empty list = nothing."""
        ...


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

def get_node_affordances(
    defn: WorkflowDef, node: NodeDef, data: dict, workflow_id: str,
    instance_id: str | None = None,
) -> list[dict]:
    """Collect affordances from all sources on a node, then number them."""
    if instance_id:
        api_base = f"/agent/{workflow_id}/{instance_id}"
    else:
        api_base = f"/agent/{workflow_id}"
    ctx = AffordanceContext(data=data, defn=defn, api_base=api_base)
    sources: list[Any] = []

    # Content: field groups (claim their member fields)
    grouped_keys: set[str] = set()
    for gdef in node.field_groups.values():
        member_fdefs = []
        for fkey in gdef.fields:
            fdef = defn.all_fields.get(fkey)
            if fdef:
                member_fdefs.append(fdef)
                grouped_keys.add(fkey)
        if member_fdefs:
            sources.append(FieldGroupSource(gdef, member_fdefs))

    # Content: ungrouped fields (individual affordances)
    field_defs = defn.node_fields(node.id)
    for fdef in field_defs.values():
        if fdef.key not in grouped_keys:
            sources.append(FieldSource(fdef))

    # Content: lists
    for list_def in node.lists.values():
        sources.append(ListSource(list_def))

    # Navigation
    for nav in node.navigation:
        sources.append(NavigationSource(nav))

    # Flow control (mutually exclusive)
    if node.fork:
        sources.append(ForkSource(node.fork))
    elif node.proceed:
        sources.append(ProceedSource(node.proceed))

    # Branch switching (when inside a fork)
    fork_state = data.get("fork_state")
    if fork_state:
        sources.append(BranchSwitchSource(fork_state))

    # Terminal actions
    for act in node.actions:
        sources.append(ActionSource(act))

    # Table (composite — delegates internally)
    if node.table is not None or node.execution:
        sources.append(TableSource(node))

    # External providers
    for pid, pnode_def in node.provider_nodes.items():
        if pnode_def.affordances:
            sources.append(ProviderSource(pid))

    # Collect
    raw: list[dict] = []
    for source in sources:
        raw.extend(source.get_affordances(ctx))

    # Assign sequential IDs
    for i, aff in enumerate(raw, 1):
        aff["id"] = i

    return raw


# ---------------------------------------------------------------------------
# Utilities (shared by sources, imported from renderer)
# ---------------------------------------------------------------------------

def _resolve_options(defn: WorkflowDef, fdef: FieldDef, data: dict, annotate: bool = True) -> list[str]:
    """Resolve options for a select field, including dynamic options."""
    if fdef.dynamic_options:
        source_key = fdef.dynamic_options.get("source_key", "")
        mapping = fdef.dynamic_options.get("mapping", {})
        source_val = data.get(source_key)
        if source_val and str(source_val) in mapping:
            return mapping[str(source_val)]
        return fdef.dynamic_options.get("default", [])

    if fdef.options:
        return fdef.options

    if fdef.options_from:
        raw_options = defn.option_sets.get(fdef.options_from, [])
        if annotate and fdef.annotate_from and fdef.annotation:
            annotate_set = set(defn.option_sets.get(fdef.annotate_from, []))
            return [
                f"{opt} {fdef.annotation}" if opt in annotate_set else opt
                for opt in raw_options
            ]
        return list(raw_options)

    return []


def _load_engine(data: dict) -> PlanEngine:
    """Hydrate a PlanEngine from table data + execution state."""
    table_data = data.get("table", {})
    columns = [ColumnDef.from_dict(c) for c in table_data.get("columns", [])]
    plan = PlanDefinition(
        cr_id="WF",
        columns=columns,
        rows=table_data.get("rows", []),
        table_properties={
            "sequentialExecution": table_data.get("properties", data.get("properties", {})).get("sequential_execution", False),
        },
    )
    exec_state = data.get("execution")
    if exec_state:
        state = ExecutionState.from_dict(exec_state)
    else:
        state = ExecutionState(cr_id="WF")
    return PlanEngine(plan, state)


# ---------------------------------------------------------------------------
# Source: Field
# ---------------------------------------------------------------------------

class FieldSource:
    """Affordances for a single field."""

    def __init__(self, fdef: FieldDef):
        self.fdef = fdef

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        fdef = self.fdef
        if not check_visibility(fdef.visible_when, ctx.data):
            return []

        ftype = fdef.type
        if ftype not in ("text", "boolean", "select"):
            return []

        current = ctx.data.get(fdef.key)
        if ftype == "boolean":
            current = bool(current)

        if isinstance(current, str) and current:
            display = f'"{trunc(current, 50)}"'
        else:
            display = json.dumps(current)

        a: dict[str, Any] = {
            "method": "POST",
            "url": f"{ctx.api_base}/{fdef.key}",
            "body": {"value": "<value>"},
            "_field_label": fdef.label,  # transient tag for partitioning
        }
        if ftype == "boolean":
            a["parameters"] = {"value": {"options": [True, False]}}
        elif ftype == "select":
            options = _resolve_options(ctx.defn, fdef, ctx.data, annotate=False)
            if options:
                a["parameters"] = {"value": {"options": options}}
        return [a]


# ---------------------------------------------------------------------------
# Source: FieldGroup
# ---------------------------------------------------------------------------

class FieldGroupSource:
    """Single affordance for a group of fields (set all at once)."""

    def __init__(self, group_def: "FieldGroupDef", field_defs: list["FieldDef"]):
        self.group_def = group_def
        self.field_defs = field_defs

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        gdef = self.group_def
        params: dict[str, Any] = {}
        body: dict[str, Any] = {}

        for fdef in self.field_defs:
            if not check_visibility(fdef.visible_when, ctx.data):
                continue
            ftype = fdef.type
            if ftype not in ("text", "boolean", "select"):
                continue

            body[fdef.key] = "<value>"
            p: dict[str, Any] = {}
            if ftype == "boolean":
                p["options"] = [True, False]
            elif ftype == "select":
                options = _resolve_options(ctx.defn, fdef, ctx.data, annotate=False)
                if options:
                    p["options"] = options
            if p:
                params[fdef.key] = p

        if not body:
            return []

        a: dict[str, Any] = {
            "method": "POST",
            "url": f"{ctx.api_base}/set_fields",
            "body": body,
            "_field_group_label": gdef.label,
        }
        if params:
            a["parameters"] = params
        return [a]


# ---------------------------------------------------------------------------
# Source: List
# ---------------------------------------------------------------------------

class ListSource:
    """Affordances for a single list."""

    def __init__(self, list_def: ListDef):
        self.list_def = list_def

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        ld = self.list_def
        api = ctx.api_base
        data = ctx.data
        items = data.get(ld.key, [])
        ops = set(ld.operations)
        affs: list[dict] = []

        # Add item
        if "add" in ops:
            body: dict[str, Any] = {}
            params: dict[str, Any] = {}
            for fkey, fld in ld.item_schema.items():
                body[fkey] = f"<{fkey}>"
                p: dict[str, Any] = {}
                if fld.options:
                    p["options"] = fld.options
                params[fkey] = p
            affs.append({
                "label": f"Add {ld.label} item",
                "method": "POST", "url": f"{api}/list_add",
                "body": {"list_key": ld.key, **body},
                "parameters": params,
            })

        if items:
            indices = list(range(len(items)))
            first_key = next(iter(ld.item_schema), None)
            labels = [
                str(item.get(first_key, i)) if isinstance(item, dict) else str(i)
                for i, item in enumerate(items)
            ]

            # Select (focus) item
            if ld.focus:
                focused = data.get(f"_focused_{ld.key}")
                focused_label = labels[focused] if focused is not None and focused < len(items) else None
                affs.append({
                    "label": f"Select {ld.label} item (focused: {json.dumps(focused_label)})",
                    "method": "POST", "url": f"{api}/list_select",
                    "body": {"list_key": ld.key, "index": "<index>"},
                    "parameters": {"index": {"options": indices, "labels": labels}},
                })

            # Edit item
            if "edit" in ops:
                params = {"index": {"options": indices, "labels": labels}}
                for fkey, fld in ld.item_schema.items():
                    p = {"description": "New value (omit to keep current)"}
                    if fld.options:
                        p["options"] = fld.options
                    params[fkey] = p
                affs.append({
                    "label": f"Edit {ld.label} item",
                    "method": "POST", "url": f"{api}/list_edit",
                    "body": {"list_key": ld.key, "index": "<index>"},
                    "parameters": params,
                })

            # Remove item
            if "remove" in ops:
                affs.append({
                    "label": f"Remove {ld.label} item",
                    "method": "POST", "url": f"{api}/list_remove",
                    "body": {"list_key": ld.key, "index": "<index>"},
                    "parameters": {"index": {"options": indices, "labels": labels}},
                })

            # Reorder item
            if "reorder" in ops and len(items) > 1:
                affs.append({
                    "label": f"Move {ld.label} item up",
                    "method": "POST", "url": f"{api}/list_reorder",
                    "body": {"list_key": ld.key, "index": "<index>", "direction": "up"},
                    "parameters": {"index": {"options": indices, "labels": labels}},
                })

        return affs


# ---------------------------------------------------------------------------
# Source: Navigation
# ---------------------------------------------------------------------------

class NavigationSource:
    """Affordance for a single navigation entry."""

    def __init__(self, nav: NavigationDef):
        self.nav = nav

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        nav = self.nav
        if nav.when:
            passed, _ = evaluate(nav.when, ctx.data)
            if not passed:
                return []
        body: dict[str, Any] = {}
        if nav.node:
            body["node"] = nav.node
        return [{
            "label": nav.label,
            "method": "POST",
            "url": f"{ctx.api_base}/{nav.action}",
            "body": body,
        }]


# ---------------------------------------------------------------------------
# Source: Proceed
# ---------------------------------------------------------------------------

class ProceedSource:
    """Affordance for the proceed gate."""

    def __init__(self, proceed: ProceedDef):
        self.proceed = proceed

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        p = self.proceed
        if p.gate:
            passed, _ = evaluate(p.gate, ctx.data)
            if not passed:
                return []
        body: dict[str, Any] = {}
        if p.target:
            body["target"] = p.target
        return [{
            "label": p.label,
            "method": "POST",
            "url": f"{ctx.api_base}/proceed",
            "body": body,
        }]


# ---------------------------------------------------------------------------
# Source: Fork
# ---------------------------------------------------------------------------

class ForkSource:
    """Affordance for a fork gate (triggers parallel branching)."""

    def __init__(self, fork: ForkDef):
        self.fork = fork

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        f = self.fork
        if f.gate:
            passed, _ = evaluate(f.gate, ctx.data)
            if not passed:
                return []
        return [{
            "label": f.label,
            "method": "POST",
            "url": f"{ctx.api_base}/proceed",
            "body": {},
        }]


# ---------------------------------------------------------------------------
# Source: BranchSwitch
# ---------------------------------------------------------------------------

class BranchSwitchSource:
    """Affordances for switching between fork branches."""

    def __init__(self, fork_state: dict):
        self.fork_state = fork_state

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        fs = self.fork_state
        fork_node = ctx.defn.nodes.get(fs.get("fork_node"))
        fork_def = fork_node.fork if fork_node else None
        active_bid = fs.get("active_branch")
        affs: list[dict] = []
        for bid, bdata in fs.get("branches", {}).items():
            if bid == active_bid or bdata.get("completed"):
                continue
            branch_label = bid
            if fork_def and bid in fork_def.branches:
                branch_label = fork_def.branches[bid].label
            affs.append({
                "label": f"Switch to {branch_label}",
                "method": "POST",
                "url": f"{ctx.api_base}/switch_branch",
                "body": {"branch": bid},
            })
        return affs


# ---------------------------------------------------------------------------
# Source: Action
# ---------------------------------------------------------------------------

class ActionSource:
    """Affordance for a terminal node action (submit, restart)."""

    def __init__(self, action: ActionDef):
        self.action = action

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        return [{
            "label": self.action.label,
            "method": "POST",
            "url": f"{ctx.api_base}/{self.action.action}",
            "body": {},
        }]


# ---------------------------------------------------------------------------
# Source: Table (composite)
# ---------------------------------------------------------------------------

class TableSource:
    """Composite source — delegates to structural or execution."""

    def __init__(self, node: NodeDef):
        self.node = node

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        if self.node.execution and ctx.data.get("execution"):
            return ExecutionSource().get_affordances(ctx)
        elif self.node.table is not None:
            return TableStructuralSource(self.node).get_affordances(ctx)
        return []


class TableStructuralSource:
    """Affordances for table construction, anchored to objects.

    Each affordance is tagged with transient keys for partitioning:
      _table_anchor: "table" | "column" | "properties"
      _col_index: <int>  (only when _table_anchor == "column")
    """

    def __init__(self, node: NodeDef):
        self.node = node

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        table_def = self.node.table
        if not table_def:
            return []

        api = ctx.api_base
        defn = ctx.defn
        data = ctx.data
        ops = set(table_def.operations)
        table_data = data.get("table", {})
        cols = table_data.get("columns", [])
        rows = table_data.get("rows", [])
        row_indices = list(range(len(rows)))
        affs: list[dict] = []

        # -- Table-level affordances --

        if "add_column" in ops:
            a: dict[str, Any] = {
                "method": "POST", "url": f"{api}/add_column",
                "body": {"name": "<name>", "type": "<type>"},
                "parameters": {"name": {}, "type": {"options": list(defn.column_types.keys())}},
                "_table_anchor": "table",
            }
            if defn.column_types:
                type_info = [
                    {"value": t, "label": info.get("label", t),
                     "category": info.get("category", ""),
                     "description": info.get("description", "")}
                    for t, info in defn.column_types.items()
                ]
                a["parameters"]["type"]["descriptions"] = type_info
            affs.append(a)

        if "add_row" in ops and cols:
            affs.append({
                "method": "POST", "url": f"{api}/add_row",
                "body": {},
                "_table_anchor": "table",
            })

        if "remove_row" in ops and rows:
            affs.append({
                "method": "POST", "url": f"{api}/remove_row",
                "body": {"row": "<row>"},
                "parameters": {"row": {"options": row_indices}},
                "_table_anchor": "table",
            })

        # -- Per-column affordances --

        exec_col_info = None  # lazily built for acceptance rules
        for ci, col in enumerate(cols):
            ctype = col.get("type", "")

            if "rename_column" in ops:
                affs.append({
                    "method": "POST", "url": f"{api}/rename_column",
                    "body": {"col": ci, "name": "<name>"},
                    "parameters": {"name": {}},
                    "_table_anchor": "column", "_col_index": ci,
                })

            if "set_column_type" in ops:
                affs.append({
                    "method": "POST", "url": f"{api}/set_column_type",
                    "body": {"col": ci, "type": "<type>"},
                    "parameters": {"type": {"options": list(defn.column_types.keys())}},
                    "_table_anchor": "column", "_col_index": ci,
                })

            if "remove_column" in ops:
                affs.append({
                    "method": "POST", "url": f"{api}/remove_column",
                    "body": {"col": ci},
                    "_table_anchor": "column", "_col_index": ci,
                })

            if "set_cell" in ops and rows:
                affs.append({
                    "method": "POST", "url": f"{api}/set_cell",
                    "body": {"col": ci, "row": "<row>", "value": "<value>"},
                    "parameters": {"row": {"options": row_indices}, "value": {}},
                    "_table_anchor": "column", "_col_index": ci,
                })

            # Type-specific: choice-list
            if "set_choices" in ops and ctype == "ex-choice-list":
                affs.append({
                    "method": "POST", "url": f"{api}/set_choices",
                    "body": {"col": ci, "choices": "<choices>"},
                    "parameters": {"choices": {"description": "Array of valid option strings"}},
                    "_table_anchor": "column", "_col_index": ci,
                })

            # Type-specific: acceptance criteria
            if "set_rule" in ops and ctype == "ae-acceptance-criteria":
                if exec_col_info is None:
                    exec_col_info = [
                        {"index": i, "name": c["name"], "type": c["type"]}
                        for i, c in enumerate(cols)
                        if c["type"] in ("ex-free-text", "ex-choice-list", "ex-cross-reference", "ex-signature")
                    ]
                affs.append({
                    "method": "POST", "url": f"{api}/set_rule",
                    "body": {"col": ci, "rule": "<rule>"},
                    "parameters": {
                        "rule": {
                            "description": 'Boolean expression tree. Structure: {"op": "AND"|"OR", "conditions": [...]}.',
                            "executable_columns": exec_col_info,
                        },
                    },
                    "_table_anchor": "column", "_col_index": ci,
                })

            # Type-specific: prerequisite
            if "set_prerequisites" in ops and ctype == "ne-prerequisite" and rows:
                row_ids = [f"Row-{i+1}" for i in range(len(rows))]
                affs.append({
                    "method": "POST", "url": f"{api}/set_prerequisites",
                    "body": {"col": ci, "row": "<row>", "prerequisites": "<prerequisites>"},
                    "parameters": {
                        "row": {"options": row_indices, "labels": row_ids},
                        "prerequisites": {"description": "Array of row indices that must pass acceptance before this row"},
                    },
                    "_table_anchor": "column", "_col_index": ci,
                })

        # -- Properties affordances --

        if "set_property" in ops:
            affs.append({
                "method": "POST", "url": f"{api}/set_property",
                "body": {"key": "sequential_execution", "value": "<value>"},
                "parameters": {"value": {"options": [True, False]}},
                "_table_anchor": "properties",
            })

        return affs


# ---------------------------------------------------------------------------
# Source: Execution
# ---------------------------------------------------------------------------

class ExecutionSource:
    """Affordances from the table execution engine (cell actions + complete)."""

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        api = ctx.api_base
        engine = _load_engine(ctx.data)
        ps = engine.get_plan_state()
        affs: list[dict] = []

        for act in ps.next_actions:
            action = act["action"]
            row = act["row"]
            col = act["col"]
            col_name = act["column_name"]
            row_id = act["row_id"]

            cell_body: dict[str, Any] = {"row": row, "col": col, "cell_action": action}
            params: dict[str, Any] = {}

            if action in ("fill", "amend"):
                cell_body["value"] = "<value>"
                col_def = engine.plan.columns[col]
                if is_choice_list(col_def.type) and col_def.choices:
                    params["value"] = {"options": col_def.choices}
                else:
                    params["value"] = {}
                label = f"{'Fill' if action == 'fill' else 'Amend'} {col_name} for {row_id}"
            elif action == "sign":
                label = f"Sign {col_name} for {row_id}"
            elif action == "re-sign":
                label = f"Re-sign {col_name} for {row_id}"
            elif action == "mark_na":
                label = f"Mark {col_name} as N/A for {row_id}"
            elif action == "initiate_issue":
                cell_body["issue_type"] = "<issue_type>"
                params["issue_type"] = {"options": ["VAR", "ER"]}
                label = f"Initiate issue for {col_name} in {row_id}"
            else:
                label = act.get("description", action)

            a: dict[str, Any] = {
                "label": label,
                "method": "POST", "url": f"{api}/cell_action",
                "body": cell_body,
            }
            if params:
                a["parameters"] = params
            affs.append(a)

        # Complete gate
        if ps.status == "completed":
            affs.append({
                "label": "Complete Execution",
                "method": "POST", "url": f"{api}/complete",
                "body": {},
            })

        return affs


# ---------------------------------------------------------------------------
# Source: Provider (external state)
# ---------------------------------------------------------------------------

class ProviderSource:
    """Adapts an ExternalStateProvider into an AffordanceSource."""

    def __init__(self, provider_id: str):
        self.provider_id = provider_id

    def get_affordances(self, ctx: AffordanceContext) -> list[dict]:
        from .providers import registry, resolve_bindings

        provider = registry.get(self.provider_id)
        if not provider:
            return []
        pdef = ctx.defn.providers.get(self.provider_id)
        if not pdef:
            return []
        cached = ctx.data.get(f"_provider_cache_{self.provider_id}")
        if cached is None:
            return []  # provider unavailable
        bindings = resolve_bindings(pdef.bindings, ctx.data)
        return provider.get_affordances(bindings, cached, ctx.api_base)
