"""YAML persistence for graphs.

REQ-WFE-024: Save graph to YAML.
REQ-WFE-025: Load graph from YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml

from wfe.graph import Edge, Field, Graph, GraphState, Node


def save(graph: Graph, path: Union[str, Path]) -> None:
    """Save a graph to a YAML file. (REQ-WFE-024)"""
    data = {
        "name": graph.name,
        "state": graph.state.value,
        "home": graph.home_id,
        "nodes": {},
    }
    for nid, node in graph.nodes.items():
        node_data: dict = {"id": node.id}
        if node.prompt:
            node_data["prompt"] = node.prompt
        if node.enter_hooks:
            node_data["enter_hooks"] = node.enter_hooks
        if node.exit_hooks:
            node_data["exit_hooks"] = node.exit_hooks
        if node.fields:
            node_data["fields"] = {
                fname: _field_to_dict(f) for fname, f in node.fields.items()
            }
        if node.edges:
            node_data["edges"] = [_edge_to_dict(e) for e in node.edges]
        data["nodes"][nid] = node_data

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load(path: Union[str, Path]) -> Graph:
    """Load a graph from a YAML file. (REQ-WFE-025)"""
    path = Path(path)
    with open(path) as f:
        data = yaml.safe_load(f)

    graph = Graph.__new__(Graph)
    graph.name = data["name"]
    graph.state = GraphState(data["state"])
    graph.home_id = data["home"]
    graph.nodes = {}

    for nid, node_data in data["nodes"].items():
        fields = {}
        for fname, fdata in node_data.get("fields", {}).items():
            fields[fname] = Field(
                name=fdata["name"],
                type=fdata["type"],
                value=fdata.get("value"),
                writable=fdata.get("writable", True),
                parameter=fdata.get("parameter", False),
            )
        edges = []
        for edata in node_data.get("edges", []):
            edges.append(Edge(
                target=edata["target"],
                condition=edata.get("condition"),
                traverse_hooks=edata.get("traverse_hooks", []),
            ))
        graph.nodes[nid] = Node(
            id=node_data["id"],
            fields=fields,
            edges=edges,
            prompt=node_data.get("prompt"),
            enter_hooks=node_data.get("enter_hooks", []),
            exit_hooks=node_data.get("exit_hooks", []),
        )

    return graph


def _field_to_dict(f: Field) -> dict:
    d: dict = {"name": f.name, "type": f.type}
    if f.value is not None:
        d["value"] = f.value
    if not f.writable:
        d["writable"] = False
    if f.parameter:
        d["parameter"] = True
    return d


def _edge_to_dict(edge: Edge) -> dict:
    d: dict = {"target": edge.target}
    if edge.condition:
        d["condition"] = edge.condition
    if edge.traverse_hooks:
        d["traverse_hooks"] = edge.traverse_hooks
    return d
