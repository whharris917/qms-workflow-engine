"""Unified Workflow Runtime.

Interprets a YAML workflow definition and implements the handler protocol
consumed by app.py. Replaces the separate handler modules (cr_handler,
generic_handler, table_handler) with a single parameterized runtime.

Usage:
    from runtime import WorkflowRuntime

    defn = yaml.safe_load(open("workflow.yaml"))
    handler = WorkflowRuntime(defn)

    data = handler.default_data()
    page = handler.render_node(data, "workflow-id")
    result = handler.process_action(data, "workflow-id", {"action": "set_field", ...})
"""

from __future__ import annotations

import yaml
from pathlib import Path

from .schema import WorkflowDef
from .compat import normalize_definition
from .renderer import render_page
from .actions import dispatch


def _table_action_label(action: str, body: dict) -> str | None:
    """Build a human-readable label for table action feedback."""
    if action == "add_column":
        return f"Add column \"{body.get('name', '')}\" ({body.get('type', '')})"
    if action == "add_row":
        return "Add row"
    if action == "set_cell":
        return f"Set cell [{body.get('row')}, {body.get('col')}]"
    if action == "rename_column":
        return f"Rename column {body.get('col')} to \"{body.get('name', '')}\""
    if action == "set_column_type":
        return f"Set column {body.get('col')} type to {body.get('type', '')}"
    if action == "remove_column":
        return f"Remove column {body.get('col')}"
    if action == "remove_row":
        return f"Remove row {body.get('row')}"
    if action == "set_property":
        return f"Set {body.get('key')} = {body.get('value')}"
    if action == "set_choices":
        return f"Set choices for column {body.get('col')}"
    if action == "set_rule":
        return f"Set acceptance rule for column {body.get('col')}"
    if action == "set_prerequisites":
        return f"Set prerequisites for cell [{body.get('row')}, {body.get('col')}]"
    if action == "cell_action":
        return f"{body.get('cell_action', '?')} on cell [{body.get('row', '?')}, {body.get('col', '?')}]"
    return action


def _build_default_data(defn: WorkflowDef) -> dict:
    """Build the initial state dict from a workflow definition."""
    d = {
        "node": defn.node_ids[0] if defn.node_ids else "",
        "completed_nodes": [],
    }
    for fdef in defn.all_fields.values():
        if fdef.type != "computed":
            d[fdef.key] = fdef.default

    # Initialize list state
    for node in defn.nodes.values():
        for list_def in node.lists.values():
            d[list_def.key] = []

    # Initialize table state if any node has a table component
    has_table = any(n.table is not None or n.execution for n in defn.nodes.values())
    if has_table:
        d["table"] = {
            "columns": [],
            "rows": [],
            "properties": {"sequential_execution": False},
        }
    return d


class WorkflowRuntime:
    """Interprets a YAML workflow definition at runtime.

    Implements the handler protocol:
        WORKFLOW_TITLE                          -> str
        VALID_RESOURCES                         -> set[str]
        default_data()                          -> dict
        render_node(data, workflow_id)          -> page dict
        process_action(data, workflow_id, body) -> page dict | error dict
        resolve_resource(resource, body)        -> (internal_body, acted_label) | None
    """

    def __init__(self, raw_definition: dict):
        normalized = normalize_definition(raw_definition)
        self.defn = WorkflowDef.from_dict(normalized)
        self.WORKFLOW_TITLE = self.defn.workflow_title

        _TABLE_RESOURCES = {
            "add_column", "add_row", "set_cell", "rename_column",
            "set_column_type", "remove_column", "remove_row",
            "set_choices", "set_rule", "set_prerequisites", "set_property",
            "cell_action", "complete",
        }
        _LIST_RESOURCES = {
            "list_add", "list_edit", "list_remove", "list_reorder", "list_select",
        }

        self.VALID_RESOURCES = (
            self.defn.all_field_keys
            | {"proceed", "go_back", "go_to", "submit", "restart", "switch_branch"}
            | _TABLE_RESOURCES
            | _LIST_RESOURCES
        )

    def default_data(self) -> dict:
        return _build_default_data(self.defn)

    def render_node(self, data: dict, workflow_id: str) -> dict:
        return render_page(self.defn, data, workflow_id)

    def process_action(self, data: dict, workflow_id: str, body: dict) -> dict:
        return dispatch(self.defn, data, workflow_id, body)

    def resolve_resource(self, resource: str, body: dict):
        """Translate a resource URL segment to (internal_body, acted_label)."""
        # Provider-routed actions: ext.{provider_id}.{action}
        if resource.startswith("ext."):
            parts = resource.split(".", 2)
            if len(parts) == 3:
                _, provider_id, action = parts
                internal_body = {
                    "action": "provider_action",
                    "provider": provider_id,
                    "provider_action": action,
                    **body,
                }
                return internal_body, f"{provider_id}: {action}"
            return None

        if resource in self.defn.all_field_keys:
            acted_label = None
            for fdef in self.defn.all_fields.values():
                if fdef.key == resource:
                    acted_label = fdef.label
                    break
            internal_body = {
                "action": "set_field",
                "field": resource,
                "value": body.get("value"),
            }
            return internal_body, acted_label

        if resource in ("proceed", "go_back", "submit", "restart", "complete"):
            return {"action": resource}, None

        if resource == "switch_branch":
            return {"action": "switch_branch", "branch": body.get("branch")}, None

        if resource == "go_to":
            return {"action": "go_to", "node": body.get("node")}, None

        # List actions
        _LIST_ACTIONS = {"list_add", "list_edit", "list_remove", "list_reorder", "list_select"}
        if resource in _LIST_ACTIONS:
            internal = dict(body)
            internal["action"] = resource
            return internal, f"{resource.replace('list_', '')} list item"

        # Table structural + execution actions
        _TABLE_BODY_ACTIONS = {
            "add_column", "add_row", "set_cell", "rename_column",
            "set_column_type", "remove_column", "remove_row",
            "set_choices", "set_rule", "set_prerequisites", "set_property",
            "cell_action",
        }
        if resource in _TABLE_BODY_ACTIONS:
            internal = dict(body)
            internal["action"] = resource
            acted_label = _table_action_label(resource, body)
            return internal, acted_label

        return None
