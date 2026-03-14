"""Create Change Record workflow handler.

Manages the CR authoring workflow through initiation, definition, scope,
impact, and pre-submission review nodes.  All rendering and action processing
is self-contained — app.py delegates to this module by workflow type.

Interface consumed by app.py:
    WORKFLOW_TITLE                          -> str
    VALID_RESOURCES                         -> set[str]
    default_data()                          -> dict (fresh state)
    render_node(data, workflow_id)          -> page dict
    process_action(data, workflow_id, body) -> page dict | error dict
    resolve_resource(resource, body)        -> (internal_body, acted_label) | None
"""

import json
from pathlib import Path

import yaml

from utils import trunc, field

# ---------------------------------------------------------------------------
# Load CR workflow definition from YAML
# ---------------------------------------------------------------------------

_YAML_PATH = Path(__file__).parent / "data" / "agent_create_cr.yaml"
with open(_YAML_PATH) as _f:
    _DEF = yaml.safe_load(_f)

_SUBMODULES = _DEF["submodules"]
_SDLC_GOVERNED = set(_DEF["sdlc_governed"])
_NODES = list(_DEF["nodes"].keys())
_LIFECYCLE = _DEF["lifecycle_banner"]

_NODE_INFO = {
    nid: {"title": n["title"], "instruction": n["instruction"]}
    for nid, n in _DEF["nodes"].items()
}
_NODE_TO_LIFECYCLE = {
    nid: n["lifecycle_label"]
    for nid, n in _DEF["nodes"].items()
}

# Aggregate all fields across all nodes (preserving declaration order)
_ALL_FIELDS = {}
_NODE_FIELDS = {}  # node_id -> {field_id: fdef}
for _nid, _ndef in _DEF["nodes"].items():
    node_fields = _ndef.get("fields", {})
    _NODE_FIELDS[_nid] = node_fields
    _ALL_FIELDS.update(node_fields)

# Known field keys (for resource-route dispatch)
_FIELD_KEYS = {fdef["key"] for fdef in _ALL_FIELDS.values()}

WORKFLOW_TITLE = "Create Change Record"
VALID_RESOURCES = _FIELD_KEYS | {"proceed", "go_back", "go_to", "submit", "restart"}

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def default_data() -> dict:
    """Return a fresh agent data dict for the CR workflow, derived from YAML."""
    d = {"node": _NODES[0], "completed_nodes": []}
    for fdef in _ALL_FIELDS.values():
        if fdef.get("type") != "computed":
            d[fdef["key"]] = fdef.get("default")
    return d


# ---------------------------------------------------------------------------
# Field visibility & summary
# ---------------------------------------------------------------------------


def _field_visible(fdef, data):
    """Evaluate whether a field's visible_when conditions are satisfied."""
    conds = fdef.get("visible_when")
    if not conds:
        return True
    for key, expected in conds.items():
        val = data.get(key)
        if expected == "not_null":
            if val is None:
                return False
        elif val != expected:
            return False
    return True


def _field_summary(data, node):
    """Return a dict of all fields relevant to the current node, including nulls."""
    node_def = _DEF["nodes"][node]
    if node_def.get("show_all_fields"):
        field_defs = _ALL_FIELDS
    else:
        field_defs = _NODE_FIELDS.get(node, {})

    fields = {}
    for fdef in field_defs.values():
        if not _field_visible(fdef, data):
            continue

        ftype = fdef.get("type", "text")
        key = fdef["key"]
        label = fdef["label"]

        if ftype == "boolean":
            value = bool(data.get(key))
            instruction = fdef.get("instruction")
        elif ftype == "computed" and fdef.get("computed") == "sdlc_check":
            value = data.get(key) in _SDLC_GOVERNED
            if value:
                instruction = fdef.get("instruction_when_true")
            else:
                instruction = fdef.get("instruction_when_false")
        else:
            value = trunc(data.get(key))
            instruction = fdef.get("instruction")

        entry = field(value, instruction)

        # Expose valid options for select fields (with annotations if defined)
        if ftype == "select":
            options_ref = fdef.get("options_ref")
            if options_ref:
                raw_options = _DEF.get(options_ref, [])
                annotate_from = fdef.get("annotate_from", "")
                annotation = fdef.get("annotation", "")
                if annotate_from and annotation:
                    annotate_set = set(_DEF.get(annotate_from, []))
                    entry["options"] = [
                        f"{opt} {annotation}" if opt in annotate_set else opt
                        for opt in raw_options
                    ]
                else:
                    entry["options"] = raw_options

        fields[label] = entry
    return fields


# ---------------------------------------------------------------------------
# Affordances
# ---------------------------------------------------------------------------


def _build_affordances(data, node, workflow_id: str):
    """Generate affordances from YAML field definitions and node config."""
    affordances = []
    n = 1
    api_url = f"/agent/{workflow_id}"
    node_def = _DEF["nodes"][node]

    # -- Field affordances --
    if node_def.get("show_all_fields"):
        field_defs = _ALL_FIELDS
    else:
        field_defs = _NODE_FIELDS.get(node, {})

    for fdef in field_defs.values():
        if not _field_visible(fdef, data):
            continue

        ftype = fdef.get("type", "text")
        key = fdef["key"]
        label = fdef["label"]

        if ftype in ("text", "boolean", "select"):
            current = data.get(key)
            if ftype == "boolean":
                current = bool(current)
            display = json.dumps(current) if not isinstance(current, str) else f'"{trunc(current, 50)}"' if current else "null"
            a = {"id": n,
                 "label": f"Set {label} (current: {display})",
                 "method": "POST", "url": f"{api_url}/{key}",
                 "body": {"value": "<value>"}}
            if ftype == "boolean":
                a["parameters"] = {"value": {"options": [True, False]}}
            elif ftype == "select":
                options_ref = fdef.get("options_ref")
                if options_ref:
                    a["parameters"] = {"value": {"options": _DEF.get(options_ref, [])}}
            affordances.append(a)
            n += 1

    # -- Navigation affordances --
    for nav in node_def.get("navigation", []):
        nav_body = {}
        if "node" in nav:
            nav_body["node"] = nav["node"]
        a = {"id": n, "label": nav["label"],
             "method": "POST", "url": f"{api_url}/{nav['action']}", "body": nav_body}
        affordances.append(a)
        n += 1

    # -- Proceed gate --
    proceed = node_def.get("proceed")
    if proceed:
        required = proceed.get("requires", [])
        if all(data.get(f) for f in required):
            a = {"id": n, "label": proceed["label"],
                 "method": "POST", "url": f"{api_url}/proceed",
                 "body": {}}
            affordances.append(a)
            n += 1

    # -- Node actions --
    for act in node_def.get("actions", []):
        a = {"id": n, "label": act["label"],
             "method": "POST", "url": f"{api_url}/{act['action']}",
             "body": {}}
        affordances.append(a)
        n += 1

    return affordances


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_node(data: dict, workflow_id: str) -> dict:
    """Render the current CR workflow node as a JSON-serializable dict."""
    node = data.get("node", _NODES[0])

    info = _NODE_INFO[node]
    affordances = _build_affordances(data, node, workflow_id)
    fields_display = _field_summary(data, node)

    lifecycle_current = _NODE_TO_LIFECYCLE.get(node, "Initiation")
    lifecycle_completed = []
    for cn in data.get("completed_nodes", []):
        lbl = _NODE_TO_LIFECYCLE.get(cn)
        if lbl and lbl not in lifecycle_completed:
            lifecycle_completed.append(lbl)

    return {
        "state": {
            "workflow": WORKFLOW_TITLE,
            "node": node,
            "node_title": info["title"],
            "lifecycle": _LIFECYCLE,
            "lifecycle_current": lifecycle_current,
            "lifecycle_completed": lifecycle_completed,
            "completed_nodes": data.get("completed_nodes", []),
            "fields": fields_display,
        },
        "instructions": info["instruction"],
        "affordances": affordances,
    }


# ---------------------------------------------------------------------------
# Action processing
# ---------------------------------------------------------------------------


def process_action(data: dict, workflow_id: str, body: dict) -> dict:
    """Process a POST action.  Mutates *data* in place.

    Returns the rendered page dict on success, or ``{"error": msg}`` on failure.
    """
    action = body.get("action")

    if action == "restart":
        fresh = default_data()
        data.clear()
        data.update(fresh)
        return render_node(data, workflow_id)

    node = data["node"]

    if action == "set_field":
        field_key = body.get("field", "")
        value = body.get("value", "")
        valid_text = [
            "title", "purpose", "scope_context", "scope_changes", "scope_files",
            "current_state", "proposed_state", "change_description", "justification",
            "impact_files", "impact_documents", "impact_other", "testing_summary",
        ]
        valid_bool = ["affects_code", "affects_submodule"]

        if field_key in valid_text:
            data[field_key] = value
        elif field_key in valid_bool:
            if value is not True and value is not False:
                return {"error": f"Invalid value for {field_key}. Must be true or false."}
            data[field_key] = value
            if field_key == "affects_code" and not value:
                data["affects_submodule"] = False
                data["submodule"] = None
            if field_key == "affects_submodule" and not value:
                data["submodule"] = None
        elif field_key == "submodule":
            if value not in _SUBMODULES:
                return {"error": f"Invalid submodule. Choose: {', '.join(_SUBMODULES)}"}
            data[field_key] = value
        else:
            return {"error": f"Unknown field: {field_key}"}

        return render_node(data, workflow_id)

    if action == "proceed":
        idx = _NODES.index(node)
        if idx >= len(_NODES) - 1:
            return {"error": "Already at the final node."}
        if node not in data["completed_nodes"]:
            data["completed_nodes"].append(node)
        data["node"] = _NODES[idx + 1]
        return render_node(data, workflow_id)

    if action == "go_back":
        idx = _NODES.index(node)
        if idx <= 0:
            return {"error": "Already at the first node."}
        data["node"] = _NODES[idx - 1]
        return render_node(data, workflow_id)

    if action == "go_to":
        target = body.get("node", "")
        if target not in _NODES:
            return {"error": f"Unknown node: {target}"}
        data["node"] = target
        return render_node(data, workflow_id)

    if action == "submit":
        if node != "preflight":
            return {"error": "You can only submit from the Pre-Submission Review node."}
        data["node"] = "submitted"
        if "preflight" not in data["completed_nodes"]:
            data["completed_nodes"].append("preflight")
        return render_node(data, workflow_id)

    return {"error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Resource-oriented endpoint translation
# ---------------------------------------------------------------------------


def resolve_resource(resource: str, body: dict):
    """Translate a resource URL segment + body into (internal_body, acted_label).

    Returns None if the resource is not recognized by this handler.
    """
    if resource in _FIELD_KEYS:
        # Look up the human-readable label for this field key
        acted_label = None
        for fdef in _ALL_FIELDS.values():
            if fdef.get("key") == resource:
                acted_label = fdef["label"]
                break
        internal_body = {"action": "set_field", "field": resource, "value": body.get("value")}
        return internal_body, acted_label

    if resource in ("proceed", "go_back", "submit", "restart"):
        return {"action": resource}, None

    if resource == "go_to":
        return {"action": "go_to", "node": body.get("node")}, None

    return None
