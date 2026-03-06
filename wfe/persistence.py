"""YAML persistence for graphs.

REQ-WFE-024: Save graph to YAML.
REQ-WFE-025: Load graph from YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml

from wfe.graph import Edge, Graph, GraphState, Node, Slot


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
        if node.slots:
            node_data["slots"] = {
                sname: _slot_to_dict(slot) for sname, slot in node.slots.items()
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
        slots = {}
        for sname, sdata in node_data.get("slots", {}).items():
            slots[sname] = Slot(
                name=sdata["name"],
                type=sdata["type"],
                value=sdata.get("value"),
                writable=sdata.get("writable", True),
            )
        edges = []
        for edata in node_data.get("edges", []):
            edges.append(Edge(
                target=edata["target"],
                condition=edata.get("condition"),
            ))
        graph.nodes[nid] = Node(
            id=node_data["id"],
            slots=slots,
            edges=edges,
            prompt=node_data.get("prompt"),
        )

    return graph


def _slot_to_dict(slot: Slot) -> dict:
    d: dict = {"name": slot.name, "type": slot.type}
    if slot.value is not None:
        d["value"] = slot.value
    if not slot.writable:
        d["writable"] = False
    return d


def _edge_to_dict(edge: Edge) -> dict:
    d: dict = {"target": edge.target}
    if edge.condition:
        d["condition"] = edge.condition
    return d
