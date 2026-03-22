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

from .runtime.evaluator import evaluate
from .runtime.schema import WorkflowDef
from .runtime.renderer import _serialize_definition

# Instance context — set at process_action() entry so internal render_node()
# calls don't need instance_id threaded through every helper.
_current_instance_id: str | None = None

# ---------------------------------------------------------------------------
# Load YAML definition for the builder's own nodes
# ---------------------------------------------------------------------------

_YAML_PATH = Path(__file__).resolve().parent.parent / "data" / "agent_create_workflow.yaml"
with open(_YAML_PATH) as _f:
    _DEF = yaml.safe_load(_f)

# Parse into WorkflowDef so we can reuse the runtime's rendering helpers.
# Inject implicit proceed links between sequential nodes so the schematic
# banner can chain them into a connected spine.
_builder_raw = {**_DEF, "workflow_title": "Create Workflow"}
_builder_node_ids = list(_builder_raw["nodes"].keys())
for _i, _nid in enumerate(_builder_node_ids[:-1]):
    # Skip preview — its only forward path is the explicit /publish action
    if _nid == "preview":
        continue
    _builder_raw["nodes"][_nid].setdefault("proceed", {"label": "Continue", "target": _builder_node_ids[_i + 1]})
_BUILDER_DEFN = WorkflowDef.from_dict(_builder_raw)

_NODES = list(_DEF["nodes"].keys())
_NODE_INFO = {
    nid: {"title": n["title"], "instruction": n["instruction"]}
    for nid, n in _DEF["nodes"].items()
}

WORKFLOW_TITLE = "Create Workflow"

_CUSTOM_DIR = Path(__file__).resolve().parent.parent / "data" / "custom_workflows"
_CUSTOM_DIR.mkdir(exist_ok=True)

_VALID_FIELD_TYPES = ["text", "boolean", "select", "computed"]

_VALID_LIST_OPS = ["add", "edit", "remove", "reorder"]

_VALID_TABLE_OPS = [
    "add_column", "remove_column", "rename_column", "set_column_type",
    "add_row", "remove_row", "set_cell", "set_choices", "set_rule",
    "set_prerequisites", "set_property",
]

_VALID_COLUMN_CATEGORIES = ["non-executable", "executable", "auto-executed"]

_EXPR_HINT = (
    'Expression dict. Leaf: {"type":"field_truthy","key":"k"}, '
    '{"type":"field_equals","key":"k","value":"v"}, '
    '{"type":"field_not_null","key":"k"}, '
    '{"type":"set_membership","key":"k","set_ref":"set_name"}, '
    '{"type":"table_has_rows"}, {"type":"table_has_columns"}. '
    'Composite: {"op":"AND"|"OR"|"NOT","conditions":[...]}.'
)

# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------


_VALID_NODE_MODES = ["standard", "router", "fork"]

def default_data() -> dict:
    return {
        "node": _NODES[0],
        "completed_nodes": [],
        "workflow_id": None,
        "workflow_title": None,
        "workflow_description": None,
        "option_sets": {},
        "column_types": {},
        "wf_nodes": [],
        "focused_node": None,
    }


def _ensure(data: dict) -> dict:
    if "node" not in data:
        return default_data()
    data.setdefault("completed_nodes", [])
    data.setdefault("wf_nodes", [])
    data.setdefault("focused_node", None)
    data.setdefault("option_sets", {})
    data.setdefault("column_types", {})
    return data


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate(data: dict) -> list[str]:
    errors = []
    wf_nodes = data.get("wf_nodes", [])
    node_ids = {n["id"] for n in wf_nodes}
    option_sets = data.get("option_sets", {})
    column_types = data.get("column_types", {})

    if not wf_nodes:
        errors.append("No nodes defined.")
        return errors

    all_keys = []
    has_exit = False

    for wn in wf_nodes:
        nid = wn["id"]
        for fld in wn.get("fields", []):
            all_keys.append(fld["key"])

        if wn.get("proceed") or wn.get("actions") or wn.get("router") or wn.get("fork"):
            has_exit = True

        # Mutual exclusion: proceed / router / fork
        exits = sum(1 for k in ("proceed", "router", "fork") if wn.get(k))
        if exits > 1:
            errors.append(f"Node '{nid}': cannot have more than one of proceed, router, fork.")

        for nav in wn.get("navigation", []):
            if "node" in nav and nav["node"] not in node_ids:
                errors.append(f"Node '{nid}': navigation target '{nav['node']}' does not exist.")

        # Router validation
        if wn.get("router"):
            for ri, route in enumerate(wn["router"]):
                if route.get("target") and route["target"] not in node_ids:
                    errors.append(f"Node '{nid}': router target '{route['target']}' does not exist.")
            if not wn["router"]:
                errors.append(f"Node '{nid}': router must have at least one route.")

        # Fork validation
        if wn.get("fork"):
            fork = wn["fork"]
            if not fork.get("branches"):
                errors.append(f"Node '{nid}': fork must have at least one branch.")
            if fork.get("merge") and fork["merge"] not in node_ids:
                errors.append(f"Node '{nid}': fork merge target '{fork['merge']}' does not exist.")
            for bid, bdef in (fork.get("branches") or {}).items():
                for bnid in bdef.get("nodes", []):
                    if bnid not in node_ids:
                        errors.append(f"Node '{nid}': fork branch '{bid}' references unknown node '{bnid}'.")

        # Table validation
        if wn.get("table"):
            tbl = wn["table"]
            cat = tbl.get("column_type_catalog")
            if cat and not column_types:
                errors.append(f"Node '{nid}': table references column_type_catalog but no column_types defined.")

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
            if proceed.get("target") and proceed["target"] not in node_ids:
                errors.append(f"Node '{wn['id']}': proceed target '{proceed['target']}' does not exist.")

        for fld in wn.get("fields", []):
            vw = fld.get("visible_when")
            if vw and isinstance(vw, dict) and "op" not in vw and "type" not in vw:
                for vk in vw:
                    if vk not in seen:
                        errors.append(f"Field '{fld['key']}': visible_when references unknown key '{vk}'.")
            if fld.get("options_from") and fld["options_from"] not in option_sets:
                errors.append(f"Field '{fld['key']}': options_from '{fld['options_from']}' not found in option_sets.")
            dyn = fld.get("dynamic_options")
            if dyn and isinstance(dyn, dict):
                sk = dyn.get("source_key")
                if sk and sk not in seen:
                    errors.append(f"Field '{fld['key']}': dynamic_options source_key '{sk}' not found in fields.")

        # List item_schema validation
        for lkey, ldef in wn.get("lists", {}).items():
            schema = ldef.get("item_schema", {})
            for fkey, finfo in schema.items():
                ftype = finfo.get("type", "text")
                if ftype not in ("text", "boolean", "select"):
                    errors.append(f"List '{lkey}' field '{fkey}': invalid type '{ftype}'.")

    if not has_exit:
        errors.append("No proceed gate, terminal action, router, or fork defined in any node.")

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
    }

    if data.get("option_sets"):
        defn["option_sets"] = data["option_sets"]
    if data.get("column_types"):
        defn["column_types"] = data["column_types"]

    defn["nodes"] = {}

    for wn in data["wf_nodes"]:
        nd = {
            "title": wn["title"],
            "instruction": wn["instruction"],
        }
        if wn.get("show_all_fields"):
            nd["show_all_fields"] = True
        if wn.get("pause") is False:
            nd["pause"] = False
        if wn.get("execution"):
            nd["execution"] = True

        # Fields
        if wn.get("fields"):
            nd["fields"] = {}
            for fld in wn["fields"]:
                fd = {"label": fld["label"], "type": fld["type"], "key": fld["key"]}
                if fld.get("default") is not None:
                    fd["default"] = fld["default"]
                if fld.get("instruction"):
                    fd["instruction"] = fld["instruction"]
                if fld["type"] == "select" and fld.get("options"):
                    fd["options"] = fld["options"]
                if fld.get("options_from"):
                    fd["options_from"] = fld["options_from"]
                if fld.get("dynamic_options"):
                    fd["dynamic_options"] = fld["dynamic_options"]
                if fld.get("side_effects"):
                    fd["side_effects"] = fld["side_effects"]
                if fld.get("visible_when"):
                    fd["visible_when"] = fld["visible_when"]
                if fld.get("compute"):
                    fd["compute"] = fld["compute"]
                if fld.get("instruction_when_true"):
                    fd["instruction_when_true"] = fld["instruction_when_true"]
                if fld.get("instruction_when_false"):
                    fd["instruction_when_false"] = fld["instruction_when_false"]
                if fld.get("annotate_from"):
                    fd["annotate_from"] = fld["annotate_from"]
                if fld.get("annotation"):
                    fd["annotation"] = fld["annotation"]
                nd["fields"][fld["key"]] = fd

        # Lists
        if wn.get("lists"):
            nd["lists"] = {}
            for lkey, ldef in wn["lists"].items():
                ld = {"label": ldef["label"], "key": lkey}
                if ldef.get("item_schema"):
                    ld["item_schema"] = ldef["item_schema"]
                if ldef.get("operations"):
                    ld["operations"] = ldef["operations"]
                if ldef.get("focus"):
                    ld["focus"] = True
                nd["lists"][lkey] = ld

        # Table
        if wn.get("table"):
            nd["table"] = wn["table"]

        if wn.get("navigation"):
            nd["navigation"] = wn["navigation"]
        if wn.get("proceed"):
            nd["proceed"] = wn["proceed"]
        if wn.get("router"):
            nd["router"] = wn["router"]
        if wn.get("fork"):
            nd["fork"] = wn["fork"]
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
    wf_nodes = data.get("wf_nodes", [])
    node_ids = [w["id"] for w in wf_nodes]
    nodes = []
    for idx, wn in enumerate(wf_nodes):
        # Resolve implicit proceed target (next sequential node)
        proceed = wn.get("proceed")
        if proceed is not None:
            proceed = dict(proceed)
            if not proceed.get("target") and idx + 1 < len(node_ids):
                proceed["target"] = node_ids[idx + 1]
        nd = {
            "id": wn["id"], "title": wn["title"],
            "instruction": wn.get("instruction", ""),
            "show_all_fields": wn.get("show_all_fields", False),
            "fields": wn.get("fields", []),
            "navigation": wn.get("navigation", []),
            "proceed": proceed,
            "actions": wn.get("actions", []),
        }
        if wn.get("pause") is False:
            nd["pause"] = False
        if wn.get("execution"):
            nd["execution"] = True
        if wn.get("lists"):
            nd["lists"] = wn["lists"]
        if wn.get("table"):
            nd["table"] = wn["table"]
        if wn.get("router"):
            nd["router"] = wn["router"]
        if wn.get("fork"):
            nd["fork"] = wn["fork"]
        nodes.append(nd)
    result = {
        "workflow_id": data.get("workflow_id"),
        "workflow_title": data.get("workflow_title"),
        "workflow_description": data.get("workflow_description"),
        "nodes": nodes,
    }
    if data.get("option_sets"):
        result["option_sets"] = data["option_sets"]
    if data.get("column_types"):
        result["column_types"] = data["column_types"]
    return result


def render_node(data: dict, workflow_id: str,
                instance_id: str | None = None) -> dict:
    data = _ensure(data)
    node = data["node"]
    info = _NODE_INFO[node]

    affordances = _build_affordances(data, workflow_id, instance_id)

    state = {
        "workflow": WORKFLOW_TITLE,
        "node": node,
        "node_title": info["title"],
        "completed_nodes": data["completed_nodes"],
        "banner_definition": _serialize_definition(_BUILDER_DEFN),
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


def _build_affordances(data: dict, workflow_id: str,
                       instance_id: str | None = None) -> list[dict]:
    node = data["node"]
    affs = []
    n = 1
    api = f"/agent/{workflow_id}/{instance_id}" if instance_id else f"/agent/{workflow_id}"

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
        option_sets = data.get("option_sets", {})
        column_types = data.get("column_types", {})

        # --- Node management ---
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

        # --- Workflow-level: option sets ---
        affs.append({"id": n, "label": f"Add option set (current: {list(option_sets.keys()) or 'none'})",
                      "method": "POST", "url": f"{api}/add_option_set",
                      "body": {"name": "<name>", "options": "<options>"},
                      "parameters": {"name": {"description": "Lowercase with underscores"}, "options": {"description": "Array of option strings"}}})
        n += 1
        if option_sets:
            affs.append({"id": n, "label": "Edit option set", "method": "POST", "url": f"{api}/edit_option_set",
                          "body": {"name": "<name>", "options": "<options>"},
                          "parameters": {"name": {"options": list(option_sets.keys())}, "options": {"description": "Array of option strings"}}})
            n += 1
            affs.append({"id": n, "label": "Remove option set", "method": "POST", "url": f"{api}/remove_option_set",
                          "body": {"name": "<name>"}, "parameters": {"name": {"options": list(option_sets.keys())}}})
            n += 1

        # --- Workflow-level: column types ---
        affs.append({"id": n, "label": f"Add column type (current: {list(column_types.keys()) or 'none'})",
                      "method": "POST", "url": f"{api}/add_column_type",
                      "body": {"type_id": "<type_id>", "label": "<label>", "category": "<category>", "description": "<description>"},
                      "parameters": {"type_id": {"description": "e.g. ex-free-text, ne-prerequisite"},
                                     "label": {}, "category": {"options": _VALID_COLUMN_CATEGORIES},
                                     "description": {}}})
        n += 1
        if column_types:
            affs.append({"id": n, "label": "Edit column type", "method": "POST", "url": f"{api}/edit_column_type",
                          "body": {"type_id": "<type_id>"},
                          "parameters": {"type_id": {"options": list(column_types.keys())},
                                         "label": {}, "category": {"options": _VALID_COLUMN_CATEGORIES},
                                         "description": {}}})
            n += 1
            affs.append({"id": n, "label": "Remove column type", "method": "POST", "url": f"{api}/remove_column_type",
                          "body": {"type_id": "<type_id>"}, "parameters": {"type_id": {"options": list(column_types.keys())}}})
            n += 1

        # --- Focused node ---
        if focused is not None and focused < len(wf_nodes):
            fn = wf_nodes[focused]
            fn_fields = fn.get("fields", [])
            all_fk = [fld["key"] for wn in wf_nodes for fld in wn.get("fields", [])]
            os_names = list(option_sets.keys())

            # Fields
            affs.append({"id": n, "label": f"Add field to '{fn['id']}'", "method": "POST", "url": f"{api}/add_field",
                          "body": {"label": "<label>", "type": "<type>", "key": "<key>"},
                          "parameters": {
                              "label": {}, "type": {"options": _VALID_FIELD_TYPES},
                              "key": {"description": "Unique state key"},
                              "instruction": {"description": "Optional guidance text"},
                              "default": {"description": "Optional default value"},
                              "options": {"description": "Array of options (select type)"},
                              "options_from": {"description": f"Reference to option_set. Available: {os_names}" if os_names else "Reference to option_set (define one first)"},
                              "dynamic_options": {"description": 'Cascading options: {"source_key":"field_key","mapping":{"val1":["opt1","opt2"]},"default":[]}'},
                              "side_effects": {"description": 'Array of [{when: <expr>, set: {field_key: value}}]. ' + _EXPR_HINT},
                              "compute": {"description": "Computed field evaluation spec. " + _EXPR_HINT},
                              "instruction_when_true": {"description": "Instruction shown when compute is true (computed type)"},
                              "instruction_when_false": {"description": "Instruction shown when compute is false (computed type)"},
                              "annotate_from": {"description": f"Annotation source set. Available: {os_names}" if os_names else "Annotation source (define option_set first)"},
                              "visible_when": {"description": "Show field conditionally. " + _EXPR_HINT},
                          }})
            n += 1

            if fn_fields:
                fi = list(range(len(fn_fields)))
                fl = [f["key"] for f in fn_fields]
                affs.append({"id": n, "label": f"Edit field in '{fn['id']}'", "method": "POST", "url": f"{api}/edit_field",
                              "body": {"field_index": "<field_index>"},
                              "parameters": {
                                  "field_index": {"options": fi, "labels": fl},
                                  "label": {}, "type": {"options": _VALID_FIELD_TYPES},
                                  "instruction": {}, "options": {},
                                  "default": {},
                                  "options_from": {"description": f"Reference to option_set. Available: {os_names}" if os_names else ""},
                                  "dynamic_options": {"description": 'Cascading: {"source_key":"field_key","mapping":{"val":["opts"]},"default":[]}'},
                                  "side_effects": {"description": 'Array of [{when: <expr>, set: {key: val}}]'},
                                  "compute": {"description": _EXPR_HINT},
                                  "instruction_when_true": {}, "instruction_when_false": {},
                                  "annotate_from": {},
                                  "visible_when": {"description": _EXPR_HINT},
                              }})
                n += 1
                affs.append({"id": n, "label": f"Remove field from '{fn['id']}'", "method": "POST", "url": f"{api}/remove_field",
                              "body": {"field_index": "<field_index>"}, "parameters": {"field_index": {"options": fi, "labels": fl}}})
                n += 1

            # Lists
            fn_lists = fn.get("lists", {})
            affs.append({"id": n, "label": f"Add list to '{fn['id']}' (current: {list(fn_lists.keys()) or 'none'})",
                          "method": "POST", "url": f"{api}/add_list",
                          "body": {"key": "<key>", "label": "<label>"},
                          "parameters": {
                              "key": {"description": "Lowercase with underscores (state key)"},
                              "label": {},
                              "operations": {"description": f"Array from: {_VALID_LIST_OPS}. Default: all."},
                              "focus": {"options": [True, False], "description": "Enable focused-item scoping"},
                          }})
            n += 1

            if fn_lists:
                lk = list(fn_lists.keys())
                affs.append({"id": n, "label": f"Edit list in '{fn['id']}'", "method": "POST", "url": f"{api}/edit_list",
                              "body": {"list_key": "<list_key>"},
                              "parameters": {"list_key": {"options": lk}, "label": {}, "operations": {"description": f"Array from: {_VALID_LIST_OPS}"}, "focus": {"options": [True, False]}}})
                n += 1
                affs.append({"id": n, "label": f"Remove list from '{fn['id']}'", "method": "POST", "url": f"{api}/remove_list",
                              "body": {"list_key": "<list_key>"}, "parameters": {"list_key": {"options": lk}}})
                n += 1

                for lkey, ldef in fn_lists.items():
                    schema = ldef.get("item_schema", {})
                    affs.append({"id": n, "label": f"Add field to list '{lkey}'", "method": "POST", "url": f"{api}/add_list_field",
                                  "body": {"list_key": lkey, "field_key": "<field_key>", "type": "<type>"},
                                  "parameters": {"field_key": {"description": "Lowercase with underscores"}, "type": {"options": ["text", "boolean", "select"]},
                                                 "required": {"options": [True, False]}, "options": {"description": "Array of options (select type)"}}})
                    n += 1
                    if schema:
                        sfk = list(schema.keys())
                        affs.append({"id": n, "label": f"Remove field from list '{lkey}'", "method": "POST", "url": f"{api}/remove_list_field",
                                      "body": {"list_key": lkey, "field_key": "<field_key>"}, "parameters": {"field_key": {"options": sfk}}})
                        n += 1

            # Table
            tbl = fn.get("table")
            if not tbl:
                ct_names = list(column_types.keys())
                affs.append({"id": n, "label": f"Set table on '{fn['id']}'", "method": "POST", "url": f"{api}/set_table",
                              "body": {},
                              "parameters": {
                                  "column_type_catalog": {"description": "Set to 'column_types' to reference workflow-level definitions" if ct_names else "Define column_types first to use a catalog"},
                                  "properties": {"description": 'Dict of table properties, e.g. {"sequential_execution":{"type":"boolean","default":false}}'},
                                  "operations": {"description": f"Array from: {_VALID_TABLE_OPS}. Default: all."},
                              }})
                n += 1
            else:
                affs.append({"id": n, "label": f"Remove table from '{fn['id']}'", "method": "POST", "url": f"{api}/remove_table", "body": {}})
                n += 1

            # Proceed gate (only in standard mode)
            if fn.get("router") is None and fn.get("fork") is None:
                other_ids = [w["id"] for w in wf_nodes if w["id"] != fn["id"]]
                affs.append({"id": n, "label": f"Set proceed gate for '{fn['id']}' (current: {json.dumps(fn.get('proceed'))})",
                              "method": "POST", "url": f"{api}/set_proceed",
                              "body": {"label": "<label>"},
                              "parameters": {
                                  "label": {},
                                  "gate": {"description": "Optional gate expression. " + _EXPR_HINT},
                                  "target": {"description": "Optional explicit next node", "options": other_ids} if other_ids else {"description": "Optional explicit next node"},
                                  "requires": {"description": f"Legacy shorthand: array of field keys -> AND gate. Available: {all_fk}"},
                              }})
                n += 1

            # Navigation
            other_ids = [w["id"] for w in wf_nodes if w["id"] != fn["id"]]
            affs.append({"id": n, "label": f"Add navigation to '{fn['id']}'", "method": "POST", "url": f"{api}/add_navigation",
                          "body": {"nav_action": "<nav_action>", "label": "<label>"},
                          "parameters": {"nav_action": {"options": ["go_back", "go_to"]}, "label": {},
                                         "node": {"options": other_ids},
                                         "when": {"description": "Optional conditional guard. " + _EXPR_HINT}}})
            n += 1

            if fn.get("navigation"):
                nvi = list(range(len(fn["navigation"])))
                nvl = [nav["label"] for nav in fn["navigation"]]
                affs.append({"id": n, "label": f"Remove navigation from '{fn['id']}'", "method": "POST", "url": f"{api}/remove_navigation",
                              "body": {"nav_index": "<nav_index>"}, "parameters": {"nav_index": {"options": nvi, "labels": nvl}}})
                n += 1

            # Actions
            affs.append({"id": n, "label": f"Add action to '{fn['id']}'", "method": "POST", "url": f"{api}/add_action",
                          "body": {"action_type": "<action_type>", "label": "<label>"}, "parameters": {"action_type": {"options": ["submit", "restart"]}, "label": {}}})
            n += 1

            if fn.get("actions"):
                ai = list(range(len(fn["actions"])))
                al = [a["label"] for a in fn["actions"]]
                affs.append({"id": n, "label": f"Remove action from '{fn['id']}'", "method": "POST", "url": f"{api}/remove_action",
                              "body": {"action_index": "<action_index>"}, "parameters": {"action_index": {"options": ai, "labels": al}}})
                n += 1

            # Node flags
            affs.append({"id": n, "label": f"Set show_all_fields for '{fn['id']}' (current: {fn.get('show_all_fields', False)})",
                          "method": "POST", "url": f"{api}/set_show_all_fields", "body": {"value": "<value>"}, "parameters": {"value": {"options": [True, False]}}})
            n += 1

            affs.append({"id": n, "label": f"Set pause for '{fn['id']}' (current: {fn.get('pause', True)})",
                          "method": "POST", "url": f"{api}/set_pause", "body": {"value": "<value>"},
                          "parameters": {"value": {"options": [True, False], "description": "True=stop here (default), False=may auto-advance if gate passes"}}})
            n += 1

            affs.append({"id": n, "label": f"Set execution for '{fn['id']}' (current: {fn.get('execution', False)})",
                          "method": "POST", "url": f"{api}/set_execution", "body": {"value": "<value>"},
                          "parameters": {"value": {"options": [True, False], "description": "True=execution node with table engine"}}})
            n += 1

            # Node mode selector
            current_mode = "router" if fn.get("router") is not None else ("fork" if fn.get("fork") else "standard")
            affs.append({"id": n, "label": f"Set node mode for '{fn['id']}' (current: {current_mode})",
                          "method": "POST", "url": f"{api}/set_node_mode", "body": {"mode": "<mode>"},
                          "parameters": {"mode": {"options": _VALID_NODE_MODES, "description": "standard=fields+proceed, router=auto-routing, fork=parallel branches"}}})
            n += 1

            # Router affordances
            if fn.get("router") is not None:
                routes = fn["router"]
                node_options = [w["id"] for w in wf_nodes if w["id"] != fn["id"]]
                affs.append({"id": n, "label": f"Add route to '{fn['id']}'", "method": "POST", "url": f"{api}/add_route",
                              "body": {"target": "<target>"},
                              "parameters": {"target": {"options": node_options},
                                             "when": {"description": "Optional condition. " + _EXPR_HINT}}})
                n += 1
                if routes:
                    ri = list(range(len(routes)))
                    rl = [f"{r.get('target', '?')} ({_fcCondLabelPy(r.get('when'))})" for r in routes]
                    affs.append({"id": n, "label": f"Remove route from '{fn['id']}'", "method": "POST", "url": f"{api}/remove_route",
                                  "body": {"route_index": "<route_index>"}, "parameters": {"route_index": {"options": ri, "labels": rl}}})
                    n += 1

            # Fork affordances
            if fn.get("fork") is not None:
                fork = fn["fork"]
                node_options = [w["id"] for w in wf_nodes if w["id"] != fn["id"]]
                affs.append({"id": n, "label": f"Set fork merge target (current: {json.dumps(fork.get('merge'))})",
                              "method": "POST", "url": f"{api}/set_fork_merge", "body": {"merge": "<merge>"},
                              "parameters": {"merge": {"options": node_options}}})
                n += 1
                affs.append({"id": n, "label": f"Set fork label (current: {json.dumps(fork.get('label'))})",
                              "method": "POST", "url": f"{api}/set_fork_label", "body": {"label": "<label>"}, "parameters": {"label": {}}})
                n += 1
                affs.append({"id": n, "label": f"Add branch to '{fn['id']}'", "method": "POST", "url": f"{api}/add_branch",
                              "body": {"branch_id": "<branch_id>", "label": "<label>", "nodes": "<nodes>"},
                              "parameters": {"branch_id": {"description": "Lowercase, underscores"}, "label": {},
                                             "nodes": {"description": f"Array of node IDs. Available: {node_options}"}}})
                n += 1
                branches = fork.get("branches", {})
                if branches:
                    bl = list(branches.keys())
                    affs.append({"id": n, "label": f"Remove branch from '{fn['id']}'", "method": "POST", "url": f"{api}/remove_branch",
                                  "body": {"branch_id": "<branch_id>"}, "parameters": {"branch_id": {"options": bl}}})
                    n += 1
                affs.append({"id": n, "label": f"Set fork gate for '{fn['id']}' (current: {json.dumps(fork.get('gate'))})",
                              "method": "POST", "url": f"{api}/set_fork_gate",
                              "body": {},
                              "parameters": {
                                  "gate": {"description": _EXPR_HINT},
                                  "requires": {"description": f"Legacy shorthand: array of field keys -> AND gate. Available: {all_fk}"},
                              }})
                n += 1

        # Builder navigation
        affs.append({"id": n, "label": "Go back to Lifecycle", "method": "POST", "url": f"{api}/go_back", "body": {}})
        n += 1

        if wf_nodes and any(wn.get("fields") or wn.get("lists") or wn.get("table") for wn in wf_nodes):
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


def process_action(data: dict, workflow_id: str, body: dict,
                   instance_id: str | None = None) -> dict:
    # Store instance_id so all internal render_node() calls can use it
    global _current_instance_id
    _current_instance_id = instance_id

    data = _ensure(data)
    action = body.get("action")
    node = data["node"]

    if action == "restart":
        fresh = default_data()
        data.clear()
        data.update(fresh)
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------

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
        return render_node(data, workflow_id, _current_instance_id)

    if action == "set_workflow_title":
        v = body.get("value", "").strip()
        if not v:
            return {"error": "Workflow title is required."}
        data["workflow_title"] = v
        return render_node(data, workflow_id, _current_instance_id)

    if action == "set_workflow_description":
        data["workflow_description"] = body.get("value", "").strip() or None
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Option sets (workflow-level)
    # -----------------------------------------------------------------------

    if action == "add_option_set":
        name = body.get("name", "").strip()
        if not name or not re.match(r"^[a-z][a-z0-9_]*$", name):
            return {"error": "Option set name must be lowercase with underscores."}
        options = body.get("options")
        if not isinstance(options, list) or not options:
            return {"error": "Options must be a non-empty array."}
        if name in data["option_sets"]:
            return {"error": f"Option set '{name}' already exists. Use edit to modify."}
        data["option_sets"][name] = options
        return render_node(data, workflow_id, _current_instance_id)

    if action == "edit_option_set":
        name = body.get("name", "").strip()
        if name not in data.get("option_sets", {}):
            return {"error": f"Option set '{name}' does not exist."}
        options = body.get("options")
        if not isinstance(options, list) or not options:
            return {"error": "Options must be a non-empty array."}
        data["option_sets"][name] = options
        return render_node(data, workflow_id, _current_instance_id)

    if action == "remove_option_set":
        name = body.get("name", "").strip()
        if name not in data.get("option_sets", {}):
            return {"error": f"Option set '{name}' does not exist."}
        del data["option_sets"][name]
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Column types (workflow-level)
    # -----------------------------------------------------------------------

    if action == "add_column_type":
        type_id = body.get("type_id", "").strip()
        if not type_id:
            return {"error": "Column type ID is required."}
        label = body.get("label", "").strip()
        category = body.get("category", "").strip()
        description = body.get("description", "").strip()
        if not label:
            return {"error": "Column type label is required."}
        if category not in _VALID_COLUMN_CATEGORIES:
            return {"error": f"Invalid category. Choose: {', '.join(_VALID_COLUMN_CATEGORIES)}"}
        if type_id in data["column_types"]:
            return {"error": f"Column type '{type_id}' already exists. Use edit to modify."}
        data["column_types"][type_id] = {"label": label, "category": category, "description": description}
        return render_node(data, workflow_id, _current_instance_id)

    if action == "edit_column_type":
        type_id = body.get("type_id", "").strip()
        if type_id not in data.get("column_types", {}):
            return {"error": f"Column type '{type_id}' does not exist."}
        ct = data["column_types"][type_id]
        if body.get("label"):
            ct["label"] = body["label"].strip()
        if body.get("category"):
            if body["category"] not in _VALID_COLUMN_CATEGORIES:
                return {"error": f"Invalid category. Choose: {', '.join(_VALID_COLUMN_CATEGORIES)}"}
            ct["category"] = body["category"]
        if body.get("description"):
            ct["description"] = body["description"].strip()
        return render_node(data, workflow_id, _current_instance_id)

    if action == "remove_column_type":
        type_id = body.get("type_id", "").strip()
        if type_id not in data.get("column_types", {}):
            return {"error": f"Column type '{type_id}' does not exist."}
        del data["column_types"][type_id]
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Node builder
    # -----------------------------------------------------------------------

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
        data["wf_nodes"].append({
            "id": nid, "title": title, "instruction": instruction,
            "show_all_fields": False, "fields": [], "lists": {},
            "table": None, "navigation": [], "proceed": None, "actions": [],
        })
        data["focused_node"] = len(data["wf_nodes"]) - 1
        return render_node(data, workflow_id, _current_instance_id)

    if action == "select_node":
        idx = body.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(data["wf_nodes"]):
            return {"error": "Invalid node index."}
        data["focused_node"] = idx
        return render_node(data, workflow_id, _current_instance_id)

    if action == "edit_node":
        idx = body.get("index")
        if not isinstance(idx, int) or idx < 0 or idx >= len(data["wf_nodes"]):
            return {"error": "Invalid node index."}
        wn = data["wf_nodes"][idx]
        if body.get("title"):
            wn["title"] = body["title"].strip()
        if body.get("instruction"):
            wn["instruction"] = body["instruction"].strip()
        return render_node(data, workflow_id, _current_instance_id)

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
        return render_node(data, workflow_id, _current_instance_id)

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
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Fields (scoped to focused node)
    # -----------------------------------------------------------------------

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
        new_field = {
            "label": label, "type": ftype, "key": key,
            "instruction": body.get("instruction", "").strip() or None,
            "default": body.get("default"),
        }
        if ftype == "select" and isinstance(body.get("options"), list):
            new_field["options"] = body["options"]
        if body.get("options_from"):
            new_field["options_from"] = body["options_from"]
        if isinstance(body.get("dynamic_options"), dict):
            new_field["dynamic_options"] = body["dynamic_options"]
        if isinstance(body.get("side_effects"), list):
            new_field["side_effects"] = body["side_effects"]
        if isinstance(body.get("visible_when"), dict):
            new_field["visible_when"] = body["visible_when"]
        if isinstance(body.get("compute"), dict):
            new_field["compute"] = body["compute"]
        if body.get("instruction_when_true"):
            new_field["instruction_when_true"] = body["instruction_when_true"]
        if body.get("instruction_when_false"):
            new_field["instruction_when_false"] = body["instruction_when_false"]
        if body.get("annotate_from"):
            new_field["annotate_from"] = body["annotate_from"]
        data["wf_nodes"][focused]["fields"].append(new_field)
        return render_node(data, workflow_id, _current_instance_id)

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
        if "default" in body:
            fld["default"] = body["default"]
        if "options_from" in body:
            fld["options_from"] = body["options_from"] or None
        if isinstance(body.get("dynamic_options"), dict):
            fld["dynamic_options"] = body["dynamic_options"]
        if isinstance(body.get("side_effects"), list):
            fld["side_effects"] = body["side_effects"]
        if isinstance(body.get("compute"), dict):
            fld["compute"] = body["compute"]
        if "instruction_when_true" in body:
            fld["instruction_when_true"] = body["instruction_when_true"] or None
        if "instruction_when_false" in body:
            fld["instruction_when_false"] = body["instruction_when_false"] or None
        if "annotate_from" in body:
            fld["annotate_from"] = body["annotate_from"] or None
        return render_node(data, workflow_id, _current_instance_id)

    if action == "remove_field":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fi = body.get("field_index")
        flds = data["wf_nodes"][focused]["fields"]
        if not isinstance(fi, int) or fi < 0 or fi >= len(flds):
            return {"error": "Invalid field index."}
        flds.pop(fi)
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Lists (scoped to focused node)
    # -----------------------------------------------------------------------

    if action == "add_list":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        key = body.get("key", "").strip()
        label = body.get("label", "").strip()
        if not key or not re.match(r"^[a-z][a-z0-9_]*$", key):
            return {"error": "List key must be lowercase with underscores."}
        if not label:
            return {"error": "List label is required."}
        fn = data["wf_nodes"][focused]
        fn.setdefault("lists", {})
        if key in fn["lists"]:
            return {"error": f"List '{key}' already exists in node '{fn['id']}'."}
        ops = body.get("operations")
        if isinstance(ops, list):
            ops = [o for o in ops if o in _VALID_LIST_OPS]
        else:
            ops = list(_VALID_LIST_OPS)
        fn["lists"][key] = {
            "label": label,
            "item_schema": {},
            "operations": ops,
            "focus": bool(body.get("focus", False)),
        }
        return render_node(data, workflow_id, _current_instance_id)

    if action == "edit_list":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        lk = body.get("list_key", "").strip()
        fn = data["wf_nodes"][focused]
        lists = fn.get("lists", {})
        if lk not in lists:
            return {"error": f"List '{lk}' does not exist."}
        ldef = lists[lk]
        if body.get("label"):
            ldef["label"] = body["label"].strip()
        if isinstance(body.get("operations"), list):
            ldef["operations"] = [o for o in body["operations"] if o in _VALID_LIST_OPS]
        if "focus" in body:
            ldef["focus"] = bool(body["focus"])
        return render_node(data, workflow_id, _current_instance_id)

    if action == "remove_list":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        lk = body.get("list_key", "").strip()
        fn = data["wf_nodes"][focused]
        lists = fn.get("lists", {})
        if lk not in lists:
            return {"error": f"List '{lk}' does not exist."}
        del lists[lk]
        return render_node(data, workflow_id, _current_instance_id)

    if action == "add_list_field":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        lk = body.get("list_key", "").strip()
        fn = data["wf_nodes"][focused]
        lists = fn.get("lists", {})
        if lk not in lists:
            return {"error": f"List '{lk}' does not exist."}
        fkey = body.get("field_key", "").strip()
        if not fkey or not re.match(r"^[a-z][a-z0-9_]*$", fkey):
            return {"error": "Field key must be lowercase with underscores."}
        schema = lists[lk].setdefault("item_schema", {})
        if fkey in schema:
            return {"error": f"Field '{fkey}' already exists in list '{lk}'."}
        ftype = body.get("type", "text")
        if ftype not in ("text", "boolean", "select"):
            return {"error": "List field type must be text, boolean, or select."}
        fdef = {"type": ftype, "required": bool(body.get("required", False))}
        if ftype == "select" and isinstance(body.get("options"), list):
            fdef["options"] = body["options"]
        schema[fkey] = fdef
        return render_node(data, workflow_id, _current_instance_id)

    if action == "remove_list_field":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        lk = body.get("list_key", "").strip()
        fn = data["wf_nodes"][focused]
        lists = fn.get("lists", {})
        if lk not in lists:
            return {"error": f"List '{lk}' does not exist."}
        fkey = body.get("field_key", "").strip()
        schema = lists[lk].get("item_schema", {})
        if fkey not in schema:
            return {"error": f"Field '{fkey}' does not exist in list '{lk}'."}
        del schema[fkey]
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Table (scoped to focused node)
    # -----------------------------------------------------------------------

    if action == "set_table":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fn = data["wf_nodes"][focused]
        tbl = {}
        cat = body.get("column_type_catalog")
        if cat:
            tbl["column_type_catalog"] = cat
        props = body.get("properties")
        if isinstance(props, dict):
            tbl["properties"] = props
        else:
            tbl["properties"] = {}
        ops = body.get("operations")
        if isinstance(ops, list):
            tbl["operations"] = [o for o in ops if o in _VALID_TABLE_OPS]
        else:
            tbl["operations"] = list(_VALID_TABLE_OPS)
        fn["table"] = tbl
        return render_node(data, workflow_id, _current_instance_id)

    if action == "remove_table":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        data["wf_nodes"][focused]["table"] = None
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Node config (scoped to focused node)
    # -----------------------------------------------------------------------

    if action == "set_proceed":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        label = body.get("label", "").strip()
        if not label:
            return {"error": "Proceed label is required."}
        proceed = {"label": label}
        gate = body.get("gate")
        requires = body.get("requires")
        if isinstance(gate, dict):
            proceed["gate"] = gate
        elif isinstance(requires, list) and requires:
            proceed["gate"] = {
                "op": "AND",
                "conditions": [{"type": "field_truthy", "key": k} for k in requires],
            }
        target = body.get("target")
        if target:
            target = target.strip() if isinstance(target, str) else target
            if not any(w["id"] == target for w in data["wf_nodes"]):
                return {"error": f"Target node '{target}' does not exist."}
            proceed["target"] = target
        data["wf_nodes"][focused]["proceed"] = proceed
        return render_node(data, workflow_id, _current_instance_id)

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
        when = body.get("when")
        if isinstance(when, dict):
            entry["when"] = when
        data["wf_nodes"][focused].setdefault("navigation", []).append(entry)
        return render_node(data, workflow_id, _current_instance_id)

    if action == "remove_navigation":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        ni = body.get("nav_index")
        navs = data["wf_nodes"][focused].get("navigation", [])
        if not isinstance(ni, int) or ni < 0 or ni >= len(navs):
            return {"error": "Invalid navigation index."}
        navs.pop(ni)
        return render_node(data, workflow_id, _current_instance_id)

    if action == "add_action":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        at = body.get("action_type", "").strip()
        al = body.get("label", "").strip()
        if at not in ("submit", "restart") or not al:
            return {"error": "action_type (submit/restart) and label are required."}
        data["wf_nodes"][focused].setdefault("actions", []).append({"action": at, "label": al})
        return render_node(data, workflow_id, _current_instance_id)

    if action == "remove_action":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        ai = body.get("action_index")
        acts = data["wf_nodes"][focused].get("actions", [])
        if not isinstance(ai, int) or ai < 0 or ai >= len(acts):
            return {"error": "Invalid action index."}
        acts.pop(ai)
        return render_node(data, workflow_id, _current_instance_id)

    if action == "set_show_all_fields":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        v = body.get("value")
        if v is not True and v is not False:
            return {"error": "value must be true or false."}
        data["wf_nodes"][focused]["show_all_fields"] = v
        return render_node(data, workflow_id, _current_instance_id)

    if action == "set_pause":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        v = body.get("value")
        if v is not True and v is not False:
            return {"error": "value must be true or false."}
        data["wf_nodes"][focused]["pause"] = v
        return render_node(data, workflow_id, _current_instance_id)

    if action == "set_execution":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        v = body.get("value")
        if v is not True and v is not False:
            return {"error": "value must be true or false."}
        data["wf_nodes"][focused]["execution"] = v
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Set node mode (standard / router / fork)
    # -----------------------------------------------------------------------

    if action == "set_node_mode":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        mode = body.get("mode", "").strip()
        if mode not in _VALID_NODE_MODES:
            return {"error": f"Invalid mode. Choose: {', '.join(_VALID_NODE_MODES)}"}
        fn = data["wf_nodes"][focused]
        # Clear conflicting properties
        if mode == "router":
            fn.pop("proceed", None)
            fn.pop("fork", None)
            fn.setdefault("router", [])
        elif mode == "fork":
            fn.pop("proceed", None)
            fn.pop("router", None)
            fn.setdefault("fork", {"label": "Continue", "merge": "", "branches": {}})
        else:  # standard
            fn.pop("router", None)
            fn.pop("fork", None)
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Router: add / remove route
    # -----------------------------------------------------------------------

    if action == "add_route":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fn = data["wf_nodes"][focused]
        if not fn.get("router") and not isinstance(fn.get("router"), list):
            return {"error": "Node is not in router mode."}
        target = body.get("target", "").strip()
        if not target or not any(w["id"] == target for w in data["wf_nodes"]):
            return {"error": f"Target node '{target}' does not exist."}
        route = {"target": target}
        when = body.get("when")
        if when and isinstance(when, dict):
            route["when"] = when
        fn["router"].append(route)
        return render_node(data, workflow_id, _current_instance_id)

    if action == "remove_route":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fn = data["wf_nodes"][focused]
        routes = fn.get("router", [])
        ri = body.get("route_index")
        if not isinstance(ri, int) or ri < 0 or ri >= len(routes):
            return {"error": "Invalid route index."}
        routes.pop(ri)
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Fork: merge, label, branch, gate
    # -----------------------------------------------------------------------

    if action == "set_fork_merge":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fn = data["wf_nodes"][focused]
        fork = fn.get("fork")
        if not fork:
            return {"error": "Node is not in fork mode."}
        merge = body.get("merge", "").strip()
        if not merge or not any(w["id"] == merge for w in data["wf_nodes"]):
            return {"error": f"Merge target '{merge}' does not exist."}
        fork["merge"] = merge
        return render_node(data, workflow_id, _current_instance_id)

    if action == "set_fork_label":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fn = data["wf_nodes"][focused]
        fork = fn.get("fork")
        if not fork:
            return {"error": "Node is not in fork mode."}
        fork["label"] = body.get("label", "Continue").strip()
        return render_node(data, workflow_id, _current_instance_id)

    if action == "add_branch":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fn = data["wf_nodes"][focused]
        fork = fn.get("fork")
        if not fork:
            return {"error": "Node is not in fork mode."}
        bid = body.get("branch_id", "").strip()
        label = body.get("label", "").strip()
        nodes_list = body.get("nodes", [])
        if not bid or not re.match(r"^[a-z][a-z0-9_]*$", bid):
            return {"error": "Branch ID must be lowercase with underscores."}
        if not label:
            return {"error": "Branch label is required."}
        if bid in fork.get("branches", {}):
            return {"error": f"Branch '{bid}' already exists."}
        # Validate node references
        node_ids = {w["id"] for w in data["wf_nodes"]}
        for nid in nodes_list:
            if nid not in node_ids:
                return {"error": f"Branch node '{nid}' does not exist."}
        fork.setdefault("branches", {})[bid] = {"label": label, "nodes": nodes_list}
        return render_node(data, workflow_id, _current_instance_id)

    if action == "remove_branch":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fn = data["wf_nodes"][focused]
        fork = fn.get("fork")
        if not fork:
            return {"error": "Node is not in fork mode."}
        bid = body.get("branch_id", "").strip()
        branches = fork.get("branches", {})
        if bid not in branches:
            return {"error": f"Branch '{bid}' does not exist."}
        del branches[bid]
        return render_node(data, workflow_id, _current_instance_id)

    if action == "set_fork_gate":
        focused = data.get("focused_node")
        if focused is None or focused >= len(data["wf_nodes"]):
            return {"error": "No node is focused."}
        fn = data["wf_nodes"][focused]
        fork = fn.get("fork")
        if not fork:
            return {"error": "Node is not in fork mode."}
        gate = body.get("gate")
        requires = body.get("requires")
        if isinstance(gate, dict):
            fork["gate"] = gate
        elif isinstance(requires, list) and requires:
            fork["gate"] = {
                "op": "AND",
                "conditions": [{"type": "field_truthy", "key": k} for k in requires],
            }
        else:
            return {"error": "Provide gate (expression dict) or requires (array of field keys)."}
        return render_node(data, workflow_id, _current_instance_id)

    # -----------------------------------------------------------------------
    # Builder navigation
    # -----------------------------------------------------------------------

    if action == "proceed":
        if node == "preview":
            return {"error": "Use 'publish' to advance from Preview."}
        idx = _NODES.index(node)
        if idx >= len(_NODES) - 1:
            return {"error": "Already at the final node."}
        if node not in data["completed_nodes"]:
            data["completed_nodes"].append(node)
        data["node"] = _NODES[idx + 1]
        return render_node(data, workflow_id, _current_instance_id)

    if action == "go_back":
        idx = _NODES.index(node)
        if idx <= 0:
            return {"error": "Already at the first node."}
        data["node"] = _NODES[idx - 1]
        return render_node(data, workflow_id, _current_instance_id)

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
        return render_node(data, workflow_id, _current_instance_id)

    return {"error": f"Unknown action: {action}"}


# ---------------------------------------------------------------------------
# Resource routing
# ---------------------------------------------------------------------------

def _fcCondLabelPy(when):
    """Build a short label for a router condition."""
    if not when:
        return "default"
    if when.get("type") == "field_equals":
        return f"{when.get('key')} = {when.get('value')}"
    if when.get("type") == "field_truthy":
        return when.get("key", "?")
    if when.get("op"):
        return f"{when['op']}(...)"
    return "?"


_SIMPLE = {"proceed", "go_back", "restart", "publish"}
_BODY = {
    "set_workflow_id", "set_workflow_title", "set_workflow_description",
    "add_node", "select_node", "edit_node", "remove_node", "reorder_node",
    "add_field", "edit_field", "remove_field",
    "set_proceed", "add_navigation", "remove_navigation",
    "add_action", "remove_action", "set_show_all_fields",
    "set_pause", "set_execution",
    "set_node_mode",
    "add_route", "remove_route",
    "set_fork_merge", "set_fork_label", "add_branch", "remove_branch", "set_fork_gate",
    "add_option_set", "edit_option_set", "remove_option_set",
    "add_column_type", "edit_column_type", "remove_column_type",
    "add_list", "edit_list", "remove_list",
    "add_list_field", "remove_list_field",
    "set_table", "remove_table",
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
