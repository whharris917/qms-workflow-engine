"""Workflow definition schema — dataclasses parsed from YAML.

These types represent the canonical form of a workflow definition.
The compat module normalizes older YAML formats into this schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FieldDef:
    """A named, typed value — the atomic unit of data collection."""
    key: str
    label: str
    type: str = "text"  # text | boolean | select | computed
    instruction: str | None = None
    default: Any = None
    options: list[str] | None = None           # select: inline options
    options_from: str | None = None            # select: reference to option_sets
    annotate_from: str | None = None           # select: mark options from this set
    annotation: str | None = None              # select: annotation string
    visible_when: dict | None = None           # condition dict
    compute: dict | None = None                # computed: evaluation spec
    instruction_when_true: str | None = None   # computed: conditional instruction
    instruction_when_false: str | None = None  # computed: conditional instruction
    side_effects: list[dict] | None = None     # [{when: expr, set: {key: val}}]
    dynamic_options: dict | None = None        # {source_key: str, mapping: {val: [options]}}

    @classmethod
    def from_dict(cls, d: dict) -> FieldDef:
        return cls(
            key=d.get("key", ""),
            label=d.get("label", ""),
            type=d.get("type", "text"),
            instruction=d.get("instruction"),
            default=d.get("default"),
            options=d.get("options"),
            options_from=d.get("options_from"),
            annotate_from=d.get("annotate_from"),
            annotation=d.get("annotation"),
            visible_when=d.get("visible_when"),
            compute=d.get("compute"),
            instruction_when_true=d.get("instruction_when_true"),
            instruction_when_false=d.get("instruction_when_false"),
            side_effects=d.get("side_effects"),
            dynamic_options=d.get("dynamic_options"),
        )


@dataclass
class TableDef:
    """Table component declaration for a node."""
    column_type_catalog: str | None = None  # reference to top-level column_types
    properties: dict = field(default_factory=dict)
    operations: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> TableDef:
        return cls(
            column_type_catalog=d.get("column_type_catalog"),
            properties=d.get("properties", {}),
            operations=d.get("operations", []),
        )


@dataclass
class NavigationDef:
    """A navigation entry within a node."""
    action: str  # go_back | go_to
    label: str
    node: str | None = None  # target node for go_to
    when: dict | None = None  # expression: suppress affordance if false

    @classmethod
    def from_dict(cls, d: dict) -> NavigationDef:
        return cls(
            action=d.get("action", ""),
            label=d.get("label", ""),
            node=d.get("node"),
            when=d.get("when"),
        )


@dataclass
class ActionDef:
    """A terminal action within a node (submit, restart)."""
    action: str
    label: str

    @classmethod
    def from_dict(cls, d: dict) -> ActionDef:
        return cls(action=d.get("action", ""), label=d.get("label", ""))


@dataclass
class ProceedDef:
    """Proceed gate definition."""
    label: str
    gate: dict | None = None   # expression tree
    target: str | None = None  # target node (if None, goes to next sequential)

    @classmethod
    def from_dict(cls, d: dict) -> ProceedDef:
        return cls(
            label=d.get("label", "Proceed"),
            gate=d.get("gate"),
            target=d.get("target"),
        )


@dataclass
class ListItemField:
    """A field within a list item schema."""
    key: str
    type: str = "text"  # text | boolean | select
    required: bool = False
    options: list[str] | None = None

    @classmethod
    def from_dict(cls, key: str, d: dict) -> ListItemField:
        return cls(
            key=key,
            type=d.get("type", "text"),
            required=d.get("required", False),
            options=d.get("options"),
        )


@dataclass
class ListDef:
    """An ordered collection with structural editing operations."""
    key: str                                   # state key for the list data
    label: str                                 # human-readable name
    item_schema: dict[str, ListItemField] = field(default_factory=dict)
    operations: list[str] = field(default_factory=list)  # add, edit, remove, reorder
    focus: bool = False                        # enable focused-item scoping

    @classmethod
    def from_dict(cls, key: str, d: dict) -> ListDef:
        schema = {}
        for fkey, fdef in (d.get("item_schema") or {}).items():
            schema[fkey] = ListItemField.from_dict(fkey, fdef)
        return cls(
            key=key,
            label=d.get("label", key),
            item_schema=schema,
            operations=d.get("operations", ["add", "edit", "remove", "reorder"]),
            focus=d.get("focus", False),
        )


@dataclass
class NodeDef:
    """A discrete step in a workflow."""
    id: str
    title: str
    instruction: str = ""
    lifecycle_label: str = ""
    show_all_fields: bool = False
    pause: bool = True  # True = always stop here; False = may auto-advance
    fields: dict[str, FieldDef] = field(default_factory=dict)
    lists: dict[str, ListDef] = field(default_factory=dict)
    table: TableDef | None = None
    execution: bool = False
    navigation: list[NavigationDef] = field(default_factory=list)
    proceed: ProceedDef | None = None
    actions: list[ActionDef] = field(default_factory=list)

    @classmethod
    def from_dict(cls, nid: str, d: dict) -> NodeDef:
        fields = {}
        for fid, fdef in (d.get("fields") or {}).items():
            fields[fid] = FieldDef.from_dict(fdef)

        lists = {}
        for lid, ldef in (d.get("lists") or {}).items():
            lists[lid] = ListDef.from_dict(lid, ldef)

        table = None
        if d.get("table"):
            table = TableDef.from_dict(d["table"])

        navigation = [NavigationDef.from_dict(n) for n in d.get("navigation", [])]
        actions = [ActionDef.from_dict(a) for a in d.get("actions", [])]

        proceed = None
        if d.get("proceed"):
            proceed = ProceedDef.from_dict(d["proceed"])

        return cls(
            id=nid,
            title=d.get("title", nid),
            instruction=d.get("instruction", ""),
            lifecycle_label=d.get("lifecycle_label", ""),
            show_all_fields=d.get("show_all_fields", False),
            pause=d.get("pause", True),
            fields=fields,
            lists=lists,
            table=table,
            execution=d.get("execution", False),
            navigation=navigation,
            proceed=proceed,
            actions=actions,
        )


@dataclass
class WorkflowDef:
    """A complete workflow definition parsed from YAML."""
    workflow_id: str
    workflow_title: str
    workflow_description: str = ""
    lifecycle_banner: list[str] = field(default_factory=list)
    option_sets: dict[str, list] = field(default_factory=dict)
    column_types: dict[str, dict] = field(default_factory=dict)
    nodes: dict[str, NodeDef] = field(default_factory=dict)

    @property
    def node_ids(self) -> list[str]:
        return list(self.nodes.keys())

    @property
    def all_fields(self) -> dict[str, FieldDef]:
        """Aggregate all fields across all nodes."""
        result = {}
        for node in self.nodes.values():
            result.update(node.fields)
        return result

    @property
    def all_field_keys(self) -> set[str]:
        return {f.key for f in self.all_fields.values()}

    def node_fields(self, node_id: str) -> dict[str, FieldDef]:
        """Fields for a specific node, or all fields if show_all_fields."""
        node = self.nodes.get(node_id)
        if not node:
            return {}
        if node.show_all_fields:
            return self.all_fields
        return node.fields

    @classmethod
    def from_dict(cls, d: dict) -> WorkflowDef:
        nodes = {}
        for nid, ndef in (d.get("nodes") or {}).items():
            nodes[nid] = NodeDef.from_dict(nid, ndef)

        return cls(
            workflow_id=d.get("workflow_id", d.get("workflow_title", "unknown")),
            workflow_title=d.get("workflow_title", "Untitled"),
            workflow_description=d.get("workflow_description", ""),
            lifecycle_banner=d.get("lifecycle_banner", []),
            option_sets=d.get("option_sets", {}),
            column_types=d.get("column_types", {}),
            nodes=nodes,
        )
