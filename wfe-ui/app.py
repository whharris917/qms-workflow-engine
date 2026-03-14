"""WFE Web UI — minimal Flask application."""

import json
import time as _time
from pathlib import Path
from queue import Queue, Empty

import yaml
import markdown
from flask import Flask, render_template, abort, request, redirect, url_for, jsonify, Response

import table_handler

app = Flask(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Register the execution API blueprint
from api import api as api_blueprint  # noqa: E402
app.register_blueprint(api_blueprint)

QUALITY_MANUAL_DIR = Path(__file__).resolve().parent.parent.parent / "Quality-Manual"


def _build_manual_toc():
    """Build a structured table of contents from the Quality Manual directory."""
    sections = []

    # Main numbered documents (sorted by filename)
    numbered = sorted(QUALITY_MANUAL_DIR.glob("[0-9]*.md"))
    for p in numbered:
        num, *rest = p.stem.split("-", 1)
        title = rest[0].replace("-", " ") if rest else p.stem
        sections.append({"slug": p.stem, "title": f"{num}. {title}", "category": "main"})

    # Key documents
    for name, title in [
        ("START_HERE", "Start Here"),
        ("QMS-Policy", "QMS Policy"),
        ("QMS-Glossary", "QMS Glossary"),
        ("FAQ", "FAQ"),
    ]:
        if (QUALITY_MANUAL_DIR / f"{name}.md").exists():
            sections.append({"slug": name, "title": title, "category": "key"})

    # Guides
    guides_dir = QUALITY_MANUAL_DIR / "guides"
    if guides_dir.exists():
        for p in sorted(guides_dir.glob("*.md")):
            title = p.stem.replace("-", " ").title()
            sections.append({"slug": f"guides/{p.stem}", "title": title, "category": "guides"})

    # Type references
    types_dir = QUALITY_MANUAL_DIR / "types"
    if types_dir.exists():
        for p in sorted(types_dir.glob("*.md")):
            sections.append({"slug": f"types/{p.stem}", "title": p.stem, "category": "types"})

    return sections


import re


def _rewrite_md_links(html, current_slug):
    """Rewrite .md links to /manual/ routes.

    Handles patterns like:
      href="03-Workflows.md"           -> /manual/03-Workflows
      href="03-Workflows.md#section"   -> /manual/03-Workflows#section
      href="../07-Child-Documents.md"  -> /manual/07-Child-Documents
      href="CR.md"                     -> /manual/types/CR  (when inside types/)
      href="../QMS-Glossary.md"        -> /manual/QMS-Glossary
    """
    current_dir = str(Path(current_slug).parent) if "/" in current_slug else ""

    def _replace(match):
        raw_path = match.group(1)
        fragment = match.group(2) or ""

        # Resolve relative path against current document's directory
        if raw_path.startswith("../"):
            # Go up one level from current dir
            rel = raw_path[3:]  # strip ../
        elif current_dir:
            rel = f"{current_dir}/{raw_path}"
        else:
            rel = raw_path

        # Strip .md extension
        slug = rel.removesuffix(".md")

        # Normalize: remove any remaining ../
        parts = []
        for part in slug.split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part and part != ".":
                parts.append(part)
        slug = "/".join(parts)

        return f'href="/manual/{slug}{fragment}"'

    return re.sub(r'href="([^"]*?\.md)(#[^"]*)?(?:")', _replace, html)


def _render_md(file_path, current_slug=""):
    """Read a markdown file and return HTML with rewritten links."""
    if not file_path.exists():
        return None
    text = file_path.read_text(encoding="utf-8")
    html = markdown.markdown(text, extensions=["tables", "fenced_code", "toc"])
    return _rewrite_md_links(html, current_slug)


@app.route("/")
def index():
    return render_template("index.html", active_page="home")


def _list_crs():
    """List all CR data files, sorted by ID."""
    crs = []
    for p in sorted(DATA_DIR.glob("CR-*.json")):
        crs.append(json.loads(p.read_text(encoding="utf-8")))
    return crs


@app.route("/qms")
def qms():
    return render_template("qms.html", active_page="qms", crs=_list_crs())


@app.route("/workspace")
def workspace():
    return render_template("workspace.html", active_page="workspace", crs=_list_crs())


@app.route("/inbox")
def inbox():
    return render_template("inbox.html", active_page="inbox")


WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / "workflows"


def _list_workflows():
    """List all workflow YAML files with name and state."""
    workflows = []
    if WORKFLOWS_DIR.exists():
        import yaml
        for p in sorted(WORKFLOWS_DIR.glob("*.yaml")):
            try:
                data = yaml.safe_load(p.read_text(encoding="utf-8"))
                workflows.append({
                    "name": data.get("name", p.stem),
                    "state": data.get("state", "unknown"),
                })
            except Exception:
                workflows.append({"name": p.stem, "state": "error"})
    return workflows


@app.route("/initiate")
def initiate():
    return render_template("initiate.html", active_page="home", workflows=_list_workflows())


# --- Template Editor ---

DOCTYPES_DIR = Path(__file__).resolve().parent / "templates" / "doctypes"
DOCTYPES_DIR.mkdir(exist_ok=True)


def _list_templates():
    """List all template YAML files."""
    templates = []
    for p in sorted(DOCTYPES_DIR.glob("*.template.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            templates.append({
                "slug": p.name.replace(".template.yaml", ""),
                "name": data.get("name", p.stem),
                "abbreviation": data.get("abbreviation", ""),
                "field_count": len(data.get("fields", [])),
            })
        except Exception:
            templates.append({"slug": p.stem, "name": p.stem, "abbreviation": "?", "field_count": 0})
    return templates


@app.route("/templates")
def template_list():
    return render_template("template_list.html", active_page="templates", templates=_list_templates())


@app.route("/template/<slug>")
def template_editor(slug):
    tpl_path = DOCTYPES_DIR / f"{slug}.template.yaml"
    if not tpl_path.exists():
        abort(404)
    tpl_data = yaml.safe_load(tpl_path.read_text(encoding="utf-8"))
    wf_path = DOCTYPES_DIR / f"{slug}.workflow.yaml"
    wf_data = yaml.safe_load(wf_path.read_text(encoding="utf-8")) if wf_path.exists() else None
    return render_template("template_editor.html", active_page="templates", slug=slug,
                           template_data=tpl_data, workflow_data=wf_data)


@app.route("/template/<slug>/save", methods=["POST"])
def template_save(slug):
    payload = request.get_json()
    if not payload:
        return {"ok": False, "error": "No data"}, 400
    tpl_data = payload.get("template")
    wf_data = payload.get("workflow")
    if tpl_data:
        path = DOCTYPES_DIR / f"{slug}.template.yaml"
        path.write_text(yaml.dump(tpl_data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
    if wf_data:
        path = DOCTYPES_DIR / f"{slug}.workflow.yaml"
        path.write_text(yaml.dump(wf_data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"ok": True}


@app.route("/template/create", methods=["POST"])
def template_create():
    payload = request.get_json()
    name = payload.get("name", "").strip()
    abbreviation = payload.get("abbreviation", "").strip().upper()
    if not abbreviation:
        return {"ok": False, "error": "Abbreviation is required"}, 400
    slug = abbreviation
    path = DOCTYPES_DIR / f"{slug}.template.yaml"
    if path.exists():
        return {"ok": False, "error": f"Template {slug} already exists"}, 409
    data = {
        "name": name or f"{abbreviation} Document",
        "abbreviation": abbreviation,
        "id_format": f"{abbreviation}-{{number:03d}}",
        "fields": [],
    }
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"ok": True, "slug": slug}


def _next_cr_number():
    """Determine the next CR number by scanning existing data files."""
    existing = sorted(DATA_DIR.glob("CR-*.json"))
    if not existing:
        return 1
    # Extract the highest number from filenames like CR-001.json
    highest = max(int(p.stem.split("-")[1]) for p in existing)
    return highest + 1


def _load_cr(cr_id):
    """Load a CR's data from disk. Returns None if not found."""
    path = DATA_DIR / f"{cr_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _save_cr(cr_id, data):
    """Save a CR's data to disk."""
    path = DATA_DIR / f"{cr_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@app.route("/create/cr")
def create_cr():
    """Initiation stage — no CR ID yet."""
    return render_template("create_cr.html", active_page="home", stage="initiation", cr=None)


@app.route("/create/cr", methods=["POST"])
def initiate_cr():
    """Handle the Initiation form: assign a CR ID and persist initial data."""
    num = _next_cr_number()
    cr_id = f"CR-{num:03d}"
    data = {
        "id": cr_id,
        "stage": "definition",
        "title": request.form.get("title", "").strip(),
        "affects_code": request.form.get("affects_code") == "on",
        "affects_submodule": request.form.get("affects_submodule") == "on",
        "submodule": request.form.get("submodule", ""),
        "purpose": request.form.get("purpose", "").strip(),
        # Remaining fields empty until Change Definition stage
        "scope_context": "",
        "scope_changes": "",
        "scope_files": "",
        "current_state": "",
        "proposed_state": "",
        "change_description": "",
        "justification": "",
        "impact_files": "",
        "impact_documents": "",
        "impact_other": "",
        "testing_summary": "",
        "implementation_plan": "",
        "eis": [],
        "plan_columns": [],
        "plan_rows": [],
        "table_properties": {},
    }
    _save_cr(cr_id, data)
    return redirect(url_for("edit_cr", cr_id=cr_id))


@app.route("/cr/<cr_id>")
def edit_cr(cr_id):
    """Change Definition stage — full form, all fields editable."""
    data = _load_cr(cr_id)
    if data is None:
        abort(404)
    return render_template("create_cr.html", active_page="home", stage="definition", cr=data)


@app.route("/cr/<cr_id>/save", methods=["POST"])
def save_cr(cr_id):
    """Save all fields for an existing CR."""
    data = _load_cr(cr_id)
    if data is None:
        abort(404)
    # Update all fields from form
    for field in [
        "title", "purpose", "scope_context", "scope_changes", "scope_files",
        "current_state", "proposed_state", "change_description", "justification",
        "impact_files", "impact_documents", "impact_other",
        "testing_summary", "implementation_plan",
    ]:
        data[field] = request.form.get(field, "").strip()
    data["affects_code"] = request.form.get("affects_code") == "on"
    data["affects_submodule"] = request.form.get("affects_submodule") == "on"
    data["submodule"] = request.form.get("submodule", "")
    _save_cr(cr_id, data)
    return redirect(url_for("edit_cr", cr_id=cr_id))


@app.route("/cr/<cr_id>/plan")
def edit_plan(cr_id):
    """Implementation Plan editor — dedicated page."""
    data = _load_cr(cr_id)
    if data is None:
        abort(404)
    # Ensure plan fields exist (for CRs created before this feature)
    data.setdefault("plan_columns", [])
    data.setdefault("plan_rows", [])
    data.setdefault("table_properties", {})
    return render_template("edit_plan.html", active_page="home", cr=data)


@app.route("/cr/<cr_id>/plan/save", methods=["POST"])
def save_plan(cr_id):
    """Save the implementation plan table data."""
    data = _load_cr(cr_id)
    if data is None:
        abort(404)
    payload = request.get_json()
    data["plan_columns"] = payload.get("columns", [])
    data["plan_rows"] = payload.get("rows", [])
    data["table_properties"] = payload.get("tableProperties", {})
    data["eis"] = data["plan_rows"]  # keep eis in sync for the CR summary
    _save_cr(cr_id, data)
    return {"ok": True}


@app.route("/sandbox")
def sandbox():
    templates = _list_templates()
    return render_template("sandbox.html", active_page="sandbox", templates=templates)


# ── Agent Portal ──

# -- Workflow registry: per-workflow state, observers --

_WORKFLOW_STATE_DIR = DATA_DIR / "workflows"
_WORKFLOW_STATE_DIR.mkdir(exist_ok=True)

# In-memory state per workflow (not persisted)
_workflow_observers: dict[str, list[Queue]] = {}
_workflow_current_path: dict[str, str | None] = {}
_workflow_last_feedback: dict[str, dict] = {}


def _wf_state_path(workflow_id: str) -> Path:
    """Return the on-disk JSON state file for a workflow."""
    return _WORKFLOW_STATE_DIR / f"{workflow_id}.state.json"


def _wf_load_state(workflow_id: str) -> dict:
    """Load workflow state from disk, or return empty dict if none."""
    p = _wf_state_path(workflow_id)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def _wf_save_state(workflow_id: str, data: dict):
    """Persist workflow state to disk."""
    p = _wf_state_path(workflow_id)
    with open(p, "w") as f:
        json.dump(data, f, indent=2)


def _wf_notify(workflow_id: str, event: dict):
    """Push event to all SSE observers for a workflow."""
    event.setdefault("timestamp", _time.time())
    dead = []
    for q in _workflow_observers.get(workflow_id, []):
        try:
            q.put_nowait(event)
        except Exception:
            dead.append(q)
    for q in dead:
        _workflow_observers[workflow_id].remove(q)


def _compute_feedback(before: dict, after: dict, acted_field_key: str = None,
                      acted_label: str = None) -> dict:
    """Compute the Feedback — structured response to an agent action.

    Returns a dict with:
      attempted_action — human-readable summary of what the agent attempted
      outcome          — the direct result: the field that was set (or error)
      effects          — cascading changes:
        new_fields          — fields that appeared as a consequence
        modified_fields     — fields that changed value as a consequence
        new_affordances     — affordance objects that became available
        modified_affordances — affordances whose presentation changed
    """
    before_fields = (before.get("state") or {}).get("fields", {})
    after_fields = (after.get("state") or {}).get("fields", {})

    # Determine which field label was directly acted upon
    if acted_label is None and acted_field_key:
        for fdef in _CR_ALL_FIELDS.values():
            if fdef.get("key") == acted_field_key:
                acted_label = fdef["label"]
                break

    outcome = {}
    new_fields = {}
    modified_fields = {}
    for label, field in after_fields.items():
        old = before_fields.get(label)
        if old is None:
            if label == acted_label:
                outcome[label] = field
            else:
                new_fields[label] = field
        elif old.get("value") != field.get("value"):
            if label == acted_label:
                outcome[label] = field
            else:
                modified_fields[label] = field

    def _aff_key(a):
        """Stable identity for an affordance — its URL."""
        return a.get("url", "")

    before_aff = {_aff_key(a): a for a in before.get("affordances", [])}
    new_affordances = []
    modified_affordances = []
    for a in after.get("affordances", []):
        key = _aff_key(a)
        if key not in before_aff:
            new_affordances.append(a)
        elif a.get("label") != before_aff[key].get("label"):
            modified_affordances.append(a)

    return {
        "outcome": outcome,
        "effects": {
            "new_fields": new_fields,
            "modified_fields": modified_fields,
            "new_affordances": new_affordances,
            "modified_affordances": modified_affordances,
        },
    }


# ---------------------------------------------------------------------------
# Create Change Record Workflow
# ---------------------------------------------------------------------------

# -- Load CR workflow definition from YAML --
_CR_YAML_PATH = Path(__file__).parent / "data" / "agent_create_cr.yaml"
with open(_CR_YAML_PATH) as _f:
    _CR_DEF = yaml.safe_load(_f)

_CR_SUBMODULES = _CR_DEF["submodules"]
_CR_SDLC_GOVERNED = set(_CR_DEF["sdlc_governed"])
_CR_NODES = list(_CR_DEF["nodes"].keys())
_CR_LIFECYCLE = _CR_DEF["lifecycle_banner"]

# Derived from the nodes dict
_CR_NODE_INFO = {
    nid: {"title": n["title"], "instruction": n["instruction"]}
    for nid, n in _CR_DEF["nodes"].items()
}
_CR_NODE_TO_LIFECYCLE = {
    nid: n["lifecycle_label"]
    for nid, n in _CR_DEF["nodes"].items()
}
# Aggregate all fields across all nodes (preserving declaration order)
_CR_ALL_FIELDS = {}
_CR_NODE_FIELDS = {}  # node_id -> {field_id: fdef}
for _nid, _ndef in _CR_DEF["nodes"].items():
    node_fields = _ndef.get("fields", {})
    _CR_NODE_FIELDS[_nid] = node_fields
    _CR_ALL_FIELDS.update(node_fields)

# -- Workflow registry --
# Each entry maps a workflow_id to its type and display metadata.
# The type determines which render/process functions handle it.
_WORKFLOWS = {
    "create-cr": {
        "type": "create-cr",
        "title": "Create Change Record",
        "description": "Author a Change Record through the full pre-approval lifecycle.",
        "renderers": ["raw", "light", "dark", "exp-a", "exp-b", "exp-c", "exp-d"],
    },
    "create-implementation-plan": {
        "type": "create-implementation-plan",
        "title": table_handler.WORKFLOW_TITLE,
        "description": "Build an execution item table for a Change Record.",
        "renderers": ["raw", "light", "dark", "exp-a", "exp-b", "exp-c", "exp-d"],
    },
}


def _cr_default_data():
    """Return a fresh agent data dict for the CR workflow, derived from YAML."""
    d = {"node": _CR_NODES[0], "completed_nodes": []}
    for fdef in _CR_ALL_FIELDS.values():
        if fdef.get("type") != "computed":
            d[fdef["key"]] = fdef.get("default")
    return d


def _cr_data(workflow_id: str) -> dict:
    """Return the current CR workflow data, initializing if needed."""
    d = _wf_load_state(workflow_id)
    if "node" not in d or "title" not in d:
        d = _cr_default_data()
        _wf_save_state(workflow_id, d)
    return d


def _trunc(val, length=80):
    """Truncate a string for display, adding ellipsis if needed."""
    if not val:
        return None
    return val[:length] + ("..." if len(val) > length else "")


def _field(value, instruction=None):
    """Build a field object with value and optional instruction."""
    f = {"value": value}
    if instruction:
        f["instruction"] = instruction
    return f


def _cr_field_visible(fdef, data):
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


def _cr_field_summary(data, node):
    """Return a dict of all fields relevant to the current node, including nulls.

    Fields are owned by their node. Nodes with show_all_fields aggregate all fields.
    """
    node_def = _CR_DEF["nodes"][node]
    if node_def.get("show_all_fields"):
        field_defs = _CR_ALL_FIELDS
    else:
        field_defs = _CR_NODE_FIELDS.get(node, {})

    fields = {}
    for fdef in field_defs.values():
        # Skip if not currently visible
        # Conditional visibility
        if not _cr_field_visible(fdef, data):
            continue

        ftype = fdef.get("type", "text")
        key = fdef["key"]
        label = fdef["label"]

        if ftype == "boolean":
            value = bool(data.get(key))
            instruction = fdef.get("instruction")
        elif ftype == "computed" and fdef.get("computed") == "sdlc_check":
            value = data.get(key) in _CR_SDLC_GOVERNED
            if value:
                instruction = fdef.get("instruction_when_true")
            else:
                instruction = fdef.get("instruction_when_false")
        else:
            value = _trunc(data.get(key))
            instruction = fdef.get("instruction")

        entry = _field(value, instruction)

        # Expose valid options for select fields (with annotations if defined)
        if ftype == "select":
            options_ref = fdef.get("options_ref")
            if options_ref:
                raw_options = _CR_DEF.get(options_ref, [])
                annotate_from = fdef.get("annotate_from", "")
                annotation = fdef.get("annotation", "")
                if annotate_from and annotation:
                    annotate_set = set(_CR_DEF.get(annotate_from, []))
                    entry["options"] = [
                        f"{opt} {annotation}" if opt in annotate_set else opt
                        for opt in raw_options
                    ]
                else:
                    entry["options"] = raw_options

        fields[label] = entry
    return fields


def _cr_build_affordances(data, node, workflow_id: str):
    """Generate affordances from YAML field definitions and node config.

    Affordance rules by field type:
      text     → "Set {label}" with placeholder as value template
      boolean  → "Set {label}" with parameters.value.options: [true, false]
      select   → "Set {label}" with parameters.value.options from YAML definition
      computed → no affordance (read-only)

    Node-level affordances (from nodes.{node} in YAML):
      navigation → always emitted
      proceed    → gated on all required fields being non-null
      actions    → unconditional
    """
    affordances = []
    n = 1
    api_url = f"/agent/{workflow_id}"
    node_def = _CR_DEF["nodes"][node]

    # -- Field affordances --
    if node_def.get("show_all_fields"):
        field_defs = _CR_ALL_FIELDS
    else:
        field_defs = _CR_NODE_FIELDS.get(node, {})

    for fdef in field_defs.values():
        if not _cr_field_visible(fdef, data):
            continue

        ftype = fdef.get("type", "text")
        key = fdef["key"]
        label = fdef["label"]

        if ftype in ("text", "boolean", "select"):
            current = data.get(key)
            if ftype == "boolean":
                current = bool(current)
            display = json.dumps(current) if not isinstance(current, str) else f'"{_trunc(current, 50)}"' if current else "null"
            a = {"id": n,
                 "label": f"Set {label} (current: {display})",
                 "method": "POST", "url": f"{api_url}/{key}",
                 "body": {"value": "<value>"}}
            if ftype == "boolean":
                a["parameters"] = {"value": {"options": [True, False]}}
            elif ftype == "select":
                options_ref = fdef.get("options_ref")
                if options_ref:
                    a["parameters"] = {"value": {"options": _CR_DEF.get(options_ref, [])}}
            affordances.append(a)
            n += 1

        # computed → no affordance

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


def _render_cr_node(workflow_id: str, node=None):
    """Render the current CR workflow node as a JSON-serializable dict."""
    data = _cr_data(workflow_id)
    if node is None:
        node = data["node"]

    info = _CR_NODE_INFO[node]
    node_idx = _CR_NODES.index(node)
    affordances = _cr_build_affordances(data, node, workflow_id)

    # Build fields display
    fields_display = _cr_field_summary(data, node)

    # Build lifecycle banner data
    lifecycle_current = _CR_NODE_TO_LIFECYCLE.get(node, "Initiation")
    lifecycle_completed = []
    for cn in data["completed_nodes"]:
        lbl = _CR_NODE_TO_LIFECYCLE.get(cn)
        if lbl and lbl not in lifecycle_completed:
            lifecycle_completed.append(lbl)

    result = {
        "state": {
            "workflow": "Create Change Record",
            "node": node,
            "node_title": info["title"],
            "lifecycle": _CR_LIFECYCLE,
            "lifecycle_current": lifecycle_current,
            "lifecycle_completed": lifecycle_completed,
            "completed_nodes": data["completed_nodes"],
            "fields": fields_display,
        },
        "instructions": info["instruction"],
        "affordances": affordances,
    }

    return result


def _process_cr_action(workflow_id: str, body):
    """Process a POST action for the Create CR workflow."""
    data = _cr_data(workflow_id)
    action = body.get("action")

    if action == "restart":
        data = _cr_default_data()
        _wf_save_state(workflow_id, data)
        return _render_cr_node(workflow_id)

    node = data["node"]

    if action == "set_field":
        field = body.get("field", "")
        value = body.get("value", "")
        valid_text = [
            "title", "purpose", "scope_context", "scope_changes", "scope_files",
            "current_state", "proposed_state", "change_description", "justification",
            "impact_files", "impact_documents", "impact_other", "testing_summary",
        ]
        valid_bool = ["affects_code", "affects_submodule"]
        valid_enum = ["submodule"]

        if field in valid_text:
            data[field] = value
        elif field in valid_bool:
            if value is not True and value is not False:
                return {"error": f"Invalid value for {field}. Must be true or false."}
            data[field] = value
            # Clear downstream fields when toggling off
            if field == "affects_code" and not value:
                data["affects_submodule"] = False
                data["submodule"] = None
            if field == "affects_submodule" and not value:
                data["submodule"] = None
        elif field == "submodule":
            if value not in _CR_SUBMODULES:
                return {"error": f"Invalid submodule. Choose: {', '.join(_CR_SUBMODULES)}"}
            data[field] = value
        else:
            return {"error": f"Unknown field: {field}"}

        _wf_save_state(workflow_id, data)
        return _render_cr_node(workflow_id)

    if action == "proceed":
        idx = _CR_NODES.index(node)
        if idx >= len(_CR_NODES) - 1:
            return {"error": "Already at the final node."}
        if node not in data["completed_nodes"]:
            data["completed_nodes"].append(node)
        data["node"] = _CR_NODES[idx + 1]
        _wf_save_state(workflow_id, data)
        page = _render_cr_node(workflow_id)
        _wf_notify(workflow_id, {"type": "navigate", "path": data["node"], "content": json.dumps(page)})
        return page

    if action == "go_back":
        idx = _CR_NODES.index(node)
        if idx <= 0:
            return {"error": "Already at the first node."}
        data["node"] = _CR_NODES[idx - 1]
        _wf_save_state(workflow_id, data)
        page = _render_cr_node(workflow_id)
        _wf_notify(workflow_id, {"type": "navigate", "path": data["node"], "content": json.dumps(page)})
        return page

    if action == "go_to":
        target = body.get("node", "")
        if target not in _CR_NODES:
            return {"error": f"Unknown node: {target}"}
        data["node"] = target
        _wf_save_state(workflow_id, data)
        page = _render_cr_node(workflow_id)
        _wf_notify(workflow_id, {"type": "navigate", "path": target, "content": json.dumps(page)})
        return page

    if action == "submit":
        if node != "preflight":
            return {"error": "You can only submit from the Pre-Submission Review node."}
        data["node"] = "submitted"
        if "preflight" not in data["completed_nodes"]:
            data["completed_nodes"].append("preflight")
        _wf_save_state(workflow_id, data)
        page = _render_cr_node(workflow_id)
        _wf_notify(workflow_id, {"type": "navigate", "path": "submitted", "content": json.dumps(page)})
        return page

    return {"error": f"Unknown action: {action}"}


def _render_agent_node(workflow_id: str):
    """Render the current state of a workflow as a JSON-serializable dict."""
    wf_type = _WORKFLOWS.get(workflow_id, {}).get("type")

    if wf_type == "create-cr":
        return _render_cr_node(workflow_id)

    if wf_type == "create-implementation-plan":
        data = _wf_load_state(workflow_id)
        if not data or "node" not in data:
            data = table_handler.default_data()
            _wf_save_state(workflow_id, data)
        return table_handler.render_node(data, workflow_id)

    return {"error": f"Unknown workflow: {workflow_id}"}


_last_action_times: dict[str, float] = {}
_ACTION_COOLDOWN: float = 1.0  # seconds between actions


def _process_agent_action(workflow_id: str, body):
    """Process a POST action for a workflow."""
    # Rate limit per workflow
    now = _time.time()
    elapsed = now - _last_action_times.get(workflow_id, 0.0)
    if elapsed < _ACTION_COOLDOWN:
        return {
            "error": f"Too fast. Wait {_ACTION_COOLDOWN - elapsed:.1f}s before your next action.",
            "retry_after": round(_ACTION_COOLDOWN - elapsed, 1),
        }
    _last_action_times[workflow_id] = now

    wf_type = _WORKFLOWS.get(workflow_id, {}).get("type")

    if wf_type == "create-cr":
        return _process_cr_action(workflow_id, body)

    if wf_type == "create-implementation-plan":
        data = _wf_load_state(workflow_id)
        if not data or "node" not in data:
            data = table_handler.default_data()
        result = table_handler.process_action(data, workflow_id, body)
        if "error" not in result:
            _wf_save_state(workflow_id, data)
        return result

    return {"error": f"Unknown workflow: {workflow_id}"}


@app.route("/agent")
def agent_portal():
    # Build workflow list with state summaries
    workflows = []
    for wf_id, wf_info in _WORKFLOWS.items():
        state = _wf_load_state(wf_id)
        has_state = bool(state)
        workflows.append({
            "id": wf_id,
            "title": wf_info["title"],
            "description": wf_info["description"],
            "has_state": has_state,
        })
    return render_template("agent.html", active_page="agent", workflows=workflows)


@app.route("/agent/<workflow_id>/observe")
def agent_observe(workflow_id):
    if workflow_id not in _WORKFLOWS:
        abort(404)
    wf_info = _WORKFLOWS[workflow_id]
    return render_template(
        "agent_observer.html",
        workflow_id=workflow_id,
        workflow_title=wf_info["title"],
        stream_url=f"/agent/{workflow_id}/stream",
        renderers=json.dumps(wf_info["renderers"]),
    )


@app.route("/agent/<workflow_id>/stream")
def agent_stream(workflow_id):
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": "Unknown workflow"}), 404

    def generate():
        q = Queue()
        observers = _workflow_observers.setdefault(workflow_id, [])
        observers.append(q)
        try:
            page = _render_agent_node(workflow_id)
            init = {
                "type": "init",
                "current_path": _workflow_current_path.get(workflow_id),
                "page": page,
                "last_feedback": _workflow_last_feedback.get(workflow_id),
            }
            yield f"data: {json.dumps(init)}\n\n"
            while True:
                try:
                    event = q.get(timeout=15)
                    yield f"data: {json.dumps(event)}\n\n"
                except Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            if q in _workflow_observers.get(workflow_id, []):
                _workflow_observers[workflow_id].remove(q)
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/agent/<workflow_id>/reset", methods=["POST"])
def agent_reset(workflow_id):
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": "Unknown workflow"}), 404
    p = _wf_state_path(workflow_id)
    if p.exists():
        p.unlink()
    _workflow_current_path.pop(workflow_id, None)
    _workflow_last_feedback.pop(workflow_id, None)
    return jsonify({"message": f"Workflow '{workflow_id}' reset."})


@app.route("/agent/<workflow_id>", methods=["GET"])
def agent_workflow_get(workflow_id):
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
    page = _render_agent_node(workflow_id)
    node = (page.get("state") or {}).get("node") or (page.get("state") or {}).get("position") or workflow_id
    _workflow_current_path[workflow_id] = node
    _wf_notify(workflow_id, {"type": "navigate", "path": node, "content": json.dumps(page)})
    if page is None:
        return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
    return jsonify(page)


def _build_attempted_action(internal_body):
    """Construct a human-readable description of what the agent attempted."""
    action = internal_body.get("action", "?")
    if action == "set_field":
        field = internal_body.get("field", "")
        value = internal_body.get("value", "")
        return f"Set {field} = \"{_trunc(str(value), 60)}\""
    return action


def _execute_and_feedback(workflow_id, internal_body, acted_field_key=None,
                          acted_label=None):
    """Execute an agent action, compute feedback, notify observers.

    Returns (feedback_dict, http_status_code).
    """
    attempted = acted_label or _build_attempted_action(internal_body)
    before_full = _render_agent_node(workflow_id)
    _wf_notify(workflow_id, {"type": "action", "path": workflow_id, "body": internal_body})
    result = _process_agent_action(workflow_id, internal_body)

    if "error" in result:
        feedback = {
            "attempted_action": attempted,
            "outcome": {"error": result["error"]},
            "effects": {
                "new_fields": {},
                "modified_fields": {},
                "new_affordances": [],
                "modified_affordances": [],
            },
        }
        _workflow_last_feedback[workflow_id] = feedback
        _wf_notify(workflow_id, {"type": "result", "path": workflow_id, "result": before_full, "feedback": feedback})
        return feedback, 422

    after_full = result
    feedback = _compute_feedback(before_full, after_full, acted_field_key=acted_field_key,
                                 acted_label=acted_label)
    feedback["attempted_action"] = attempted

    node = (after_full.get("state") or {}).get("node") or (after_full.get("state") or {}).get("position") or workflow_id
    _workflow_current_path[workflow_id] = node
    _workflow_last_feedback[workflow_id] = feedback
    _wf_notify(workflow_id, {"type": "result", "path": workflow_id, "result": after_full, "feedback": feedback})

    return feedback, 200


# Known CR field keys (for resource-route dispatch)
_CR_FIELD_KEYS = {fdef["key"] for fdef in _CR_ALL_FIELDS.values()}


@app.route("/agent/<workflow_id>/<resource>", methods=["POST"])
def agent_resource_post(workflow_id, resource):
    """Resource-oriented endpoint — each affordance is a literal URL."""
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
    body = request.get_json(silent=True) or {}
    wf_type = _WORKFLOWS[workflow_id]["type"]
    acted_field_key = None
    acted_label = None

    if wf_type == "create-cr":
        if resource in _CR_FIELD_KEYS:
            internal_body = {"action": "set_field", "field": resource, "value": body.get("value")}
            acted_field_key = resource
        elif resource in ("proceed", "go_back", "submit", "restart"):
            internal_body = {"action": resource}
        elif resource == "go_to":
            internal_body = {"action": "go_to", "node": body.get("node")}
        else:
            return jsonify({"error": f"Unknown resource: {resource}"}), 404

    elif wf_type == "create-implementation-plan":
        resolved = table_handler.resolve_resource(resource, body)
        if resolved is None:
            return jsonify({"error": f"Unknown resource: {resource}"}), 404
        internal_body, acted_label = resolved

    else:
        return jsonify({"error": f"Unknown workflow type"}), 404

    feedback, status = _execute_and_feedback(workflow_id, internal_body,
                                             acted_field_key=acted_field_key,
                                             acted_label=acted_label)
    return jsonify(feedback), status


@app.route("/agent/<workflow_id>", methods=["POST"])
def agent_workflow_post(workflow_id):
    """Legacy single-endpoint dispatch (backward compatibility)."""
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
    body = request.get_json(silent=True) or {}
    acted_field_key = body.get("field") if body.get("action") == "set_field" else None
    feedback, status = _execute_and_feedback(workflow_id, body, acted_field_key=acted_field_key)
    return jsonify(feedback), status


@app.route("/manual")
def manual_index():
    toc = _build_manual_toc()
    return render_template("manual_index.html", active_page="manual", toc=toc)


@app.route("/manual/<path:slug>")
def manual_page(slug):
    file_path = QUALITY_MANUAL_DIR / f"{slug}.md"
    html_content = _render_md(file_path, current_slug=slug)
    if html_content is None:
        abort(404)
    toc = _build_manual_toc()
    title = file_path.stem.replace("-", " ").replace("_", " ")
    return render_template(
        "manual_page.html",
        active_page="manual",
        toc=toc,
        content=html_content,
        page_title=title,
        current_slug=slug,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
