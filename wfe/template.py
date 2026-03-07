"""Template system for reusable node definitions.

A template defines a node structure with parameter fields
(required at instantiation) and constant fields (fixed values).
Symbolic edge targets ({next}, {var}, {vr}) are resolved to
actual node IDs via an edge_map at instantiation time. Edges
whose targets are not in the edge_map are omitted — this allows
the same template to be used in simple chains (no VAR/VR) and
full CR workflows (with VAR/VR branching).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from wfe.graph import Edge, Graph, Node

TEMPLATES_DIR = Path("templates")


@dataclass
class FieldSpec:
    """Field definition in a template."""

    name: str
    type: str
    writable: bool = True
    parameter: bool = False   # Must be supplied at instantiation
    default: Any = None       # Value set at instantiation if not a parameter


@dataclass
class EdgeTemplate:
    """Symbolic edge in a template. Target is resolved at instantiation."""

    to: str           # Symbolic: "{next}", "{var}", "{vr}", or literal node ID
    condition: Optional[str] = None
    spawns_workflow: Optional[str] = None  # Workflow definition ID this edge may spawn


@dataclass
class Template:
    """A reusable node definition."""

    id: str
    field_specs: list[FieldSpec] = field(default_factory=list)
    edge_templates: list[EdgeTemplate] = field(default_factory=list)
    prompt: Optional[str] = None
    label: Optional[str] = None  # Display label for compiled output
    enter_hooks: list[str] = field(default_factory=list)
    exit_hooks: list[str] = field(default_factory=list)


class TemplateLibrary:
    """Loads and provides access to templates from a directory."""

    def __init__(self, templates_dir: Path = TEMPLATES_DIR):
        self.dir = templates_dir
        self._templates: dict[str, Template] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.dir.exists():
            for yaml_path in sorted(self.dir.glob("*.yaml")):
                tmpl = _load_template(yaml_path)
                self._templates[tmpl.id] = tmpl
        self._loaded = True

    def get(self, template_id: str) -> Template:
        self._ensure_loaded()
        if template_id not in self._templates:
            raise KeyError(f"Template '{template_id}' not found in {self.dir}/")
        return self._templates[template_id]

    def list_ids(self) -> list[str]:
        self._ensure_loaded()
        return list(self._templates.keys())


def _load_template(path: Path) -> Template:
    with open(path) as f:
        data = yaml.safe_load(f)

    field_specs = []
    for fdata in data.get("fields", []):
        field_specs.append(FieldSpec(
            name=fdata["name"],
            type=fdata["type"],
            writable=fdata.get("writable", True),
            parameter=fdata.get("parameter", False),
            default=fdata.get("default"),
        ))

    edge_templates = []
    for edata in data.get("edge_templates", []):
        edge_templates.append(EdgeTemplate(
            to=edata["to"],
            condition=edata.get("condition"),
            spawns_workflow=edata.get("spawns_workflow"),
        ))

    return Template(
        id=data["id"],
        field_specs=field_specs,
        edge_templates=edge_templates,
        prompt=data.get("prompt"),
        label=data.get("label"),
        enter_hooks=data.get("enter_hooks", []),
        exit_hooks=data.get("exit_hooks", []),
    )


def instantiate(
    template: Template,
    graph: Graph,
    params: dict[str, Any] | None = None,
    edge_map: dict[str, str] | None = None,
    name_prefix: str | None = None,
) -> Node:
    """Instantiate a template as a new node in a draft graph.

    Args:
        template: The template to instantiate.
        graph: The draft graph to add the node to.
        params: Values for parameter fields. Required if template has parameters.
        edge_map: Maps symbolic targets ("{next}", "{var}") to actual node IDs.
                  Edges whose symbolic targets are not in edge_map are omitted.
        name_prefix: Optional prefix for the generated node ID.

    Returns:
        The newly created Node.
    """
    params = params or {}
    edge_map = edge_map or {}
    prefix = name_prefix or template.id

    node = graph.add_node(prefix)
    node.template_id = template.id
    node.label = template.label
    if template.prompt:
        node.prompt = template.prompt
    node.enter_hooks = list(template.enter_hooks)
    node.exit_hooks = list(template.exit_hooks)

    for spec in template.field_specs:
        if spec.parameter:
            if spec.name not in params:
                raise ValueError(
                    f"Parameter '{spec.name}' required for template '{template.id}'."
                )
            value = params[spec.name]
        else:
            value = spec.default
        graph.add_field(
            node.id, spec.name, spec.type, value=value,
            writable=spec.writable, parameter=spec.parameter,
        )

    # Add edges. Subprocess edges (spawns_workflow set) are kept even when
    # their symbolic target doesn't resolve — they're hand-off references, not
    # graph navigation. Normal edges are omitted when unresolved.
    for et in template.edge_templates:
        target = edge_map.get(et.to, et.to)
        is_symbolic = target.startswith("{") and target.endswith("}")
        in_graph = target in graph.nodes

        if not is_symbolic and in_graph:
            e = graph.add_edge(node.id, target, et.condition)
            e.spawns_workflow = et.spawns_workflow
        elif et.spawns_workflow:
            # Subprocess edge: target may be unresolved or absent — keep as reference
            node.edges.append(
                Edge(target=target, condition=et.condition, spawns_workflow=et.spawns_workflow)
            )
        # else: unresolved, no subprocess — omit

    return node
