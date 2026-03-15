"""Create Workflow workflow handler (v2 — uses runtime utilities).

The meta-tool for building new workflows. Uses the unified runtime's
expression evaluator and rendering helpers, but keeps its own structural
editing logic since it manages a nested definition (nodes containing
fields) that doesn't map to the standard field/table primitives.

Interface consumed by app.py — same handler protocol as all others.
"""

import json
import re
from pathlib import Path

import yaml

from runtime.evaluator import evaluate
from runtime.renderer import render_page as _unused  # type: ignore — we render our own way

# ---------------------------------------------------------------------------
# Load YAML definition for the builder's own nodes
# ---------------------------------------------------------------------------

_YAML_PATH = Path(__file__).parent / "data" / "agent_create_workflow.yaml"
with open(_YAML_PATH) as _f:
    _DEF = yaml.safe_load(_f)

_NODES = list(_DEF["nodes"].keys())
_NODE_INFO = {
    nid: {"title": n["title"], "instruction": n["instruction"]}
    for nid, n in _DEF["nodes"].items()
}

WORKFLOW_TITLE = "Create Workflow"

_CUSTOM_DIR = Path(__file__).parent / "data" / "custom_workflows"
_CUSTOM_DIR.mkdir(exist_ok=True)

_VALID_FIELD_TYPES = ["text", "boolean", "select"]

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


def default_data() -> dict:
    return {
        "node": _NODES[0],
        "completed_nodes": [],
        "workflow_id": None,
        "workflow_title": None,
        "workflow_description": None,
        "wf_nodes": [],
        "focused_node": None,
    }


def _ensure(data: dict) -> dict:
    if "node" not in data:
        return default_data()
    data.setdefault("completed_nodes", [])
    data.setdefault("wf_nodes", [])
    data.setdefault("focused_node", None)
    return data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate(data: dict) -> list[str]:
    errors = []
    wf_nodes = data.get("wf_nodes", [])
    node_ids = {n["id"] for n in wf_nodes}

    if not wf_nodes:
        errors.append("No nodes defined.")
        return errors

    all_keys = []
    has_proceed_or_action = False

    for wn in wf_nodes:
        for fld in wn.get("fields", []):
            all_keys.append(fld["key"])

        if wn.get("proceed"):
            has_proceed_or_action = True
        if wn.get("actions"):
            has_proceed_or_action = True

        for nav in wn.get("navigation", []):
            if "node" in nav and nav["node"] not in node_ids:
                errors.append(f"Node '{nid}': navigation target '{nav['node']}' does not exist.")

    seen = set()
    for key in all_keys:
        if key in seen:
            errors.append(f"Duplicate field key: '{key}'.")
        seen.add(key)

    for wn in wf_nodes:
        proceed = wn.get("proceed")
        if proceed:
            for rk in proceed.get("requires", []):
                if rk not in seen:
                    errors.append(f"Node '{wn['id']}': proceed requires unknown key '{rk}'.")

        for fld in wn.get("fields", []):
            if fld.get("visible_when"):
                for vk in fld["visible_when"]:
                    if vk not in seen:
                        errors.append(f"Field '{fld['key']}': visible_when references unknown key '{vk}'.")

    if not has_proceed_or_action:
        errors.append("No proceed gate or terminal action defined in any node.")

    return errors


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------


def _publish(data: dict) -> str | None:
    wf_id = data["workflow_id"]
    out_path = _CUSTOM_DIR / f"{wf_id}.yaml"

    defn = {
        "workflow_title": data["workflow_title"],
        "workflow_description": data["workflow_description"] or "",
        "nodes": {},
    }

    for wn in data["wf_nodes"]:
        nd = {
            "title": wn["title"],
            "instruction": wn["instruction"],
        }
        if wn.get("show_all_fields"):
            nd["show_all_fields"] = True
        if wn.get("fields"):
            nd["fields"] = {}
            for fld in wn["fields"]:
                fd = {"label": fld["label"], "type": fld["type"], "key": fld["key"], "default": fld.get("default")}
                if fld.get("instruction"):
                    fd["instruction"] = fld["instruction"]
                if fld["type"] == "select" and fld.get("options"):
                    fd["options"] = fld["options"]
                if fld.get("visible_when"):
                    fd["visible_when"] = fld["visible_when"]
                nd["fields"][fld["key"]] = fd
        if wn.get("navigation"):
            nd["navigation"] = wn["navigation"]
        if wn.get("proceed"):
            nd["proceed"] = wn["proceed"]
        if wn.get("actions"):
            nd["actions"] = wn["actions"]
        defn["nodes"][wn["id"]] = nd

    try:
        with open(out_path, "w") as f:
            yaml.dump(defn, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        return None
    except Exception as e:
        return str(e)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _summary(data: dict) -> dict:
    return {
        "workflow_id": data.get("workflow_id"),
        "workflow_title": data.get("workflow_title"),
        "workflow_description": data.get("workflow_description"),
        "nodes": [
            {
                "id": wn["id"], "title": wn["title"],
                "instruction": wn.get("instruction", ""),
                "show_all_fields": wn.get("show_all_fields", False),
                "fields": wn.get("fields", []),
                "navigation": wn.get("navigation", []),
                "proceed": wn.get("proceed"),
                "actions": wn.get("actions", []),
            }
            for wn in data.get("wf_nodes", [])
        ],
    }


def render_node(data: dict, workflow_id: str) -> dict:
    data = _ensure(data)
    node = data["node"]
    info = _NODE_INFO[node]

    # Derive lifecycle from builder's own node titles
    lifecycle = [_NODE_INFO[nid]["title"] for nid in _NODES]
    lifecycle_current = info["title"]
    lifecycle_completed = []
    for cn in data["completed_nodes"]:
        cn_info = _NODE_INFO.get(cn)
        if cn_info and cn_info["title"] not in lifecycle_completed:
            lifecycle_completed.append(cn_info["title"])

    affordances = _build_affordances(data, workflow_id)

    state = {
        "workflow": WORKFLOW_TITLE,
        "node": node,
        "node_title": info["title"],
        "lifecycle": lifecycle,
        "lifecycle_current": lifecycle_current,
        "lifecycle_completed": lifecycle_completed,
        "completed_nodes": data["completed_nodes"],
        "definition": _summary(data),
    }

    if node == "preview":
        state["validation_errors"] = _validate(data)

    return {
        "state": state,
        "instructions": info["instruction"],
        "affordances": affordances,
    }


# ---------------------------------------------------------------------------
# Affordances
# ---------------------------------------------------------------------------


def _build_affordances(data: dict, workflow_id: str) -> list[dict]:
    node = data["node"]
    affs = []
    n = 1
    api = f"/agent/{workflow_id}"

    if node == "metadata":
        for key, label in [("workflow_id", "Workflow ID"), ("workflow_title", "Workflow Title"), ("workflow_description", "Workflow Description")]:
            affs.append({
                "id": n, "label": f"Set {label} (current: {json.dumps(data.get(key))})",
                "method": "POST", "url": f"{api}/set_{key}",
                "body": {"value": "<value>"}, "parameters": {"value": {}},
            })
            n += 1
        if data.get("workflow_id") and data.get("workflow_title"):
            affs.append({"id": n, "label": "Proceed to Lifecycle", "method": "POST", "url": f"{api}/proceed", "body": {}})
            n += 1

    elif node == "node_builder":
        wf_nodes = data.get("wf_nodes", [])
        focused = data.get("focused_node")

        affs.append({"id": n, "label": "Add node", "method": "POST", "url": f"{api}/add_node",
                      "body": {"id": "<id>", "title": "<title>", "instruction": "<instruction>"},
                      "parameters": {"id": {"description": "Lowercase, underscores"}, "title": {}, "instruction": {}}})
        n += 1

        if wf_nodes:
            ni = list(range(len(wf_nodes)))
            nl = [w["id"] for w in wf_nodes]
            affs.append({"id": n, "label": f"Select node to edit (focused: {json.dumps(wf_nodes[focused]['id'] if focused is not None and focused < len(wf_nodes) else None)})",
                          "method": "POST", "url": f"{api}/select_node", "body": {"index": "<index>"}, "parameters": {"index": {"options": ni, "labels": nl}}})
            n += 1
            affs.append({"id": n, "label": "Edit node", "method": "POST", "url": f"{api}/edit_node",
                          "body": {"index": "<index>"}, "parameters": {"index": {"options": ni, "labels": nl}, "title": {}, "instruction": {}}})
            n += 1
            affs.append({"id": n, "label": "Remove node", "method": "POST", "url": f"{api}/remove_node", "body": {"index": "<index>"}, "parameters": {"index": {"options": ni, "labels": nl}}})
            n += 1
            if len(wf_nodes) > 1:
                affs.append({"id": n, "label": "Move node up", "method": "POST", "url": f"{api}/reorder_node", "body": {"index": "<index>", "direction": "up"}, "parameters": {"index": {"options": ni, "labels": nl}}})
                n += 1

        if focused is not None and focused < len(wf_nodes):
            fn = wf_nodes[focused]
            fn_fields = fn.get("fields", [])
            all_fk = [fld["key"] for wn in wf_nodes for fld in wn.get("fields", [])]

            affs.append({"id": n, "label": f"Add field to '{fn['id']}'", "method": "POST", "url": f"{api}/add_field",
                          "body": {"label": "<label>", "type": "<type>", "key": "<key>"},
                          "parameters": {"label": {}, "type": {"options": _VALID_FIELD_TYPES}, "key": {"description": "Unique state key"}}})
            n += 1

            if fn_fields:
                fi = list(range(len(fn_fields)))
                fl = [f["key"] for f in fn_fields]
                affs.append({"id": n, "label": f"Edit field in '{fn['id']}'", "method": "POST", "url": f"{api}/edit_field",
                              "body": {"field_index": "<field_index>"}, "parameters": {"field_index": {"options": fi, "labels": fl}, "label": {}, "type": {"options": _VALID_FIELD_TYPES}, "instruction": {}, "options": {}, "visible_when": {}}})
                n += 1
                affs.append({"id": n, "label": f"Remove field from '{fn['id']}'", "method": "POST", "url": f"{api}/remove_field",
                              "body": {"field_index": "<field_index>"}, "parameters": {"field_index": {"options": fi, "labels": fl}}})
                n += 1

            if all_fk:
                affs.append({"id": n, "label": f"Set proceed gate for '{fn['id']}' (current: {json.dumps(fn.get('proceed'))})",
                              "method": "POST", "url": f"{api}/set_proceed", "body": {"label": "<label>", "requires": "<requires>"},
                              "parameters": {"label": {}, "requires": {"description": f"Array of required field keys. Available: {all_fk}"}}})
                n += 1

            other_ids = [w["id"] for w in wf_nodes if w["id"] != fn["id"]]
            affs.append({"id": n, "label": f"Add navigation to '{fn['id']}'", "method": "POST", "url": f"{api}/add_navigation",
                          "body": {"nav_action": "<nav_action>", "label": "<label>"},
                          "parameters": {"nav_action": {"options": ["go_back", "go_to"]}, "label": {}, "node": {"options": other_ids}}})
            n += 1

            if fn.get("navigation"):
                nvi = list(range(len(fn["navigation"])))
                nvl = [nav["label"] for nav in fn["navigation"]]
                affs.append({"id": n, "label": f"Remove navigation from '{fn['id']}'", "method": "POST", "url": f"{api}/remove_navigation",
                              "body": {"nav_index": "<nav_index>"}, "parameters": {"nav_index": {"options": nvi, "labels": nvl}}})
                n += 1

            affs.append({"id": n, "label": f"Add action to '{fn['id']}'", "method": "POST", "url": f"{api}/add_action",
                          "body": {"action_type": "<action_type>", "label": "<label>"}, "parameters": {"action_type": {"options": ["submit", "restart"]}, "label": {}}})
            n += 1

            if fn.get("actions"):
                ai = list(range(len(fn["actions"])))
                al = [a["label"] for a in fn["actions"]]
                affs.append({"id": n, "label": f"Remove action from '{fn['id']}'", "method": "POST", "url": f"{api}/remove_action",
                              "body": {"action_index": "<action_index>"}, "parameters": {"action_index": {"options": ai, "labels": al}}})
                n += 1

            affs.append({"id": n, "label": f"Set show_all_fields for '{fn['id']}' (current: {fn.get('show_all_fields', False)})",
                          "method": "POST", "url": f"{api}/set_show_all_fields", "body": {"value": "<value>"}, "parameters": {"value": {"options": [True, False]}}})
            n += 1

        affs.append({"id": n, "label": "Go back to Lifecycle", "method": "POST", "url": f"{api}/go_back", "body": {}})
        n += 1

        if wf_nodes and any(wn.get("fields") for wn in wf_nodes):
            affs.append({"id": n, "label": "Proceed to Preview", "method": "POST", "url": f"{api}/proceed", "body": {}})
            n += 1

    elif node == "preview":
        affs.append({"id": n, "label": "Go back to Node Builder", "method": "POST", "url": f"{api}/go_back", "body": {}})
        n += 1
        if not _validate(data):
            affs.append({"id": n, "label": "Publish Workflow", "method": "POST", "url": f"{api}/publish", "body": {}})
            n += 1

    elif node == "published":
        affs.append({"id": n, "label": "Start a new Workflow", "method": "POST", "url": f"{api}/restart", "body": {}})
        n += 1

    return affs


# ---------------------------------------------------------------------------
# Action processing
# ---------------------------------------------------------------------------


def process_action(data: dict, workflow_id: str, body: dict) -> dict:
    data = _ensure(data)
    action = body.get("action")
    node = data["node"]

    if action == "restart":
        fresh = default_data()
        data.clear()
        data.update(fresh)
        return render_node(data, workflow_id)

    # Metadata
    if action == "set_workflow_id":
        v = body.get("value", "").strip()
        if not v:
            return {"error": "Workflow ID is required."}
        if not re.match(r"^[a-z][a-z0-9-]*$", v):
            return {"error": "Lowercase with hyphens only, starting with a letter."}
        reserved = {"create-cr", "create-executable-table", "create-workflow"}
        if v in reserved:
            return {"error": f"'{v}' is a reserved workflow ID."}
        data["workflow_id"] = v
        return render_node(data, workflow_id)

    if action == "set_workflow_title":
        v = body.get("value", "").strip()
        if not v:
            return {"error": "Workflow title is required."}
        data["workflow_title"] = v
        return render_node(data, workflow_id)

    if action == "set_workflow_description":
        data["workflow_description"] = body.get("value", "").strip() or None
        return render_node(data, workflow_id)

    # Node builder
    if action == "add_node":
        nid = body.get("id", "").strip()
        title = body.get("title", "").strip()
        instruction = body.get("instruction", "").strip()
        if not nid or not re.match(r"^[a-z][a-z0-9_]*$", nid):
            return {"error": "Node ID must be lowercase with underscores."}
        if any(w["id"] == nid for w in data["wf_nodes"]):
            return {"error": f"Node '{nid}' already exists."}
        if not title:
            return {"error": "Node title is required."}
        data["wf_nodes"].append({"id": nid, "title": title, "instruction": instruction, "show_all_fields": False, "fields": [], "navigation": [], "proceed": None, "actions": []})
        data["focused_node"] = len(data["wf_nodes"]) - 1
        return render_node(data, workflow_id)

    if action == "select_node":
        idx = body.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(data["wf_nodes"]):
            return {"error": "Invalid node index."}
        data["focused_node"] = idx
        return render_node(data, workflow_id)

    if action == "edit_node":
        idx = body.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(data["wf_nodes"]):
            return {"error": "Invalid node index."}
        wn = data["wf_nodes"][idx]
        if body.get("title"):
            wn["title"] = body["title"].strip()
        if body.get("instruction"):
            wn["instruction"] = body["instruction"].strip()
        return render_node(data, workflow_id)

    if action == "remove_node":
        idx = body.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(data["wf_nodes"]):
            return {"error": "Invalid node index."}
        data["wf_nodes"].pop(idx)
        if data["focused_node"] is not None:
            if data["focused_node"] == idx:
                data["focused_node"] = None
            elif data["focused_node"] > idx:
                data["focused_node"] -= 1
        return render_node(data, workflow_id)

    if action == "reorder_node":
        idx = body.get("index")
        direction = body.get("direction", "up")
        wns = data["wf_nodes"]
        if not isinstance(idx, int) or idx < 0 or idx >= len(wns):
            return {"error": "Invalid node index."}
        if direction == "up" and idx > 0:
            wns[idx], wns[idx-1] = wns[idx-1], wns[idx]
            if data["focused_node"] == idx:
                data["focused_node"] = idx - 1
            elif data["focused_node"] == idx - 1:
                data["focused_node"] = idx
        elif direction == "down" and idx < len(wns) - 1:
            wns[idx], wns[idx+1] = wns[idx+1], wns[idx]
            if data["focused_node"] == idx:
                data["focused_node"] = idx + 1
            elif data["focused_node"] == idx + 1:
                data["focused_node"] = idx
        return render_node(data, workflow_id)

    # Fields (scoped to focused node)
    if action == "add_field":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        label = body.get("label", "").strip()
        ftype = body.get("type", "text")
        key = body.get("key", "").strip()
        if not label or not key:
            return {"error": "Field label and key are required."}
        if not re.match(r"^[a-z][a-z0-9_]*$", key):
            return {"error": "Key must be lowercase with underscores."}
        if ftype not in _VALID_FIELD_TYPES:
            return {"error": f"Invalid type. Choose: {', '.join(_VALID_FIELD_TYPES)}"}
        for wn in data["wf_nodes"]:
            for fld in wn.get("fields", []):
                if fld["key"] == key:
                    return {"error": f"Key '{key}' already exists in node '{wn['id']}'."}
        new_field = {"label": label, "type": ftype, "key": key, "instruction": body.get("instruction", "").strip() or None, "default": None}
        if ftype == "select" and isinstance(body.get("options"), list):
            new_field["options"] = body["options"]
        data["wf_nodes"][focused]["fields"].append(new_field)
        return render_node(data, workflow_id)

    if action == "edit_field":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fi = body.get("field_index")
        flds = data["wf_nodes"][focused]["fields"]
        if not isinstance(fi, int) or fi < 0 or fi >= len(flds):
            return {"error": "Invalid field index."}
        fld = flds[fi]
        if body.get("label"):
            fld["label"] = body["label"].strip()
        if body.get("type") and body["type"] in _VALID_FIELD_TYPES:
            fld["type"] = body["type"]
        if "instruction" in body:
            fld["instruction"] = body["instruction"].strip() or None
        if isinstance(body.get("options"), list):
            fld["options"] = body["options"]
        if isinstance(body.get("visible_when"), dict):
            fld["visible_when"] = body["visible_when"]
        return render_node(data, workflow_id)

    if action == "remove_field":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fi = body.get("field_index")
        flds = data["wf_nodes"][focused]["fields"]
        if not isinstance(fi, int) or fi < 0 or fi >= len(flds):
            return {"error": "Invalid field index."}
        flds.pop(fi)
        return render_node(data, workflow_id)

    # Node config (scoped to focused node)
    if action == "set_proceed":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        label = body.get("label", "").strip()
        requires = body.get("requires")
        if not label or not isinstance(requires, list):
            return {"error": "Proceed label and requires array are required."}
        data["wf_nodes"][focused]["proceed"] = {"label": label, "requires": requires}
        return render_node(data, workflow_id)

    if action == "add_navigation":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        na = body.get("nav_action", "").strip()
        nl = body.get("label", "").strip()
        if na not in ("go_back", "go_to") or not nl:
            return {"error": "nav_action (go_back/go_to) and label are required."}
        entry = {"action": na, "label": nl}
        if na == "go_to":
            target = body.get("node", "").strip()
            if not target or not any(w["id"] == target for w in data["wf_nodes"]):
                return {"error": f"Target node '{target}' does not exist."}
            entry["node"] = target
        data["wf_nodes"][focused].setdefault("navigation", []).append(entry)
        return render_node(data, workflow_id)

    if action == "remove_navigation":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        ni = body.get("nav_index")
        navs = data["wf_nodes"][focused].get("navigation", [])
        if not isinstance(ni, int) or ni < 0 or ni >= len(navs):
            return {"error": "Invalid navigation index."}
        navs.pop(ni)
        return render_node(data, workflow_id)

    if action == "add_action":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        at = body.get("action_type", "").strip()
        al = body.get("label", "").strip()
        if at not in ("submit", "restart") or not al:
            return {"error": "action_type (submit/restart) and label are required."}
        data["wf_nodes"][focused].setdefault("actions", []).append({"action": at, "label": al})
        return render_node(data, workflow_id)

    if action == "remove_action":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        ai = body.get("action_index")
        acts = data["wf_nodes"][focused].get("actions", [])
        if not isinstance(ai, int) or ai < 0 or ai >= len(acts):
            return {"error": "Invalid action index."}
        acts.pop(ai)
        return render_node(data, workflow_id)

    if action == "set_show_all_fields":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        v = body.get("value")
        if v is not True and v is not False:
            return {"error": "value must be true or false."}
        data["wf_nodes"][focused]["show_all_fields"] = v
        return render_node(data, workflow_id)

    # Navigation
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

    if action == "publish":
        if node != "preview":
            return {"error": "Can only publish from Preview."}
        errors = _validate(data)
        if errors:
            return {"error": "Validation failed: " + "; ".join(errors)}
        err = _publish(data)
        if err:
            return {"error": f"Failed to write YAML: {err}"}
        if "preview" not in data["completed_nodes"]:
            data["completed_nodes"].append("preview")
        data["node"] = "published"
        return render_node(data, workflow_id)

    return {"error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Resource routing
# ---------------------------------------------------------------------------

_SIMPLE = {"proceed", "go_back", "restart", "publish"}
_BODY = {
    "set_workflow_id", "set_workflow_title", "set_workflow_description",
    "add_node", "select_node", "edit_node", "remove_node", "reorder_node",
    "add_field", "edit_field", "remove_field",
    "set_proceed", "add_navigation", "remove_navigation",
    "add_action", "remove_action", "set_show_all_fields",
}
VALID_RESOURCES = _SIMPLE | _BODY


def resolve_resource(resource: str, body: dict):
    if resource in _SIMPLE:
        return {"action": resource}, None
    if resource in _BODY:
        internal = dict(body)
        internal["action"] = resource
        return internal, resource.replace("_", " ").title()
    return None
