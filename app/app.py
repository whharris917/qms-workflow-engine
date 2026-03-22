"""WFE Web UI — minimal Flask application."""

import json
import time as _time
import uuid
from pathlib import Path
from queue import Queue, Empty

import yaml
import markdown
from flask import Flask, render_template, abort, request, redirect, url_for, jsonify, Response

from engine import builder as builder_handler
from engine.runtime import WorkflowRuntime


app = Flask(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Register the execution API blueprint
from app.api import api as api_blueprint  # noqa: E402
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


@app.route("/initiate")
def initiate():
    return render_template("initiate.html", active_page="home", workflows=[])


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

# -- Workflow registry: per-instance state, observers --

_WORKFLOW_STATE_DIR = DATA_DIR / "workflows"
_WORKFLOW_STATE_DIR.mkdir(exist_ok=True)


def _cache_key(workflow_id: str, instance_id: str) -> str:
    """Composite key for in-memory caches."""
    return f"{workflow_id}/{instance_id}"


# In-memory state per workflow instance (not persisted)
_workflow_observers: dict[str, list[Queue]] = {}
_workflow_current_path: dict[str, str | None] = {}
_workflow_last_feedback: dict[str, dict] = {}


def _wf_new_instance_id() -> str:
    """Generate a new instance ID (8-char hex from UUID4)."""
    return uuid.uuid4().hex[:8]


def _wf_instance_dir(workflow_id: str) -> Path:
    """Return (and create) the directory for a workflow type's instances."""
    d = _WORKFLOW_STATE_DIR / workflow_id
    d.mkdir(exist_ok=True)
    return d


def _wf_state_path(workflow_id: str, instance_id: str) -> Path:
    """Return the on-disk JSON state file for a workflow instance."""
    return _wf_instance_dir(workflow_id) / f"{instance_id}.state.json"


def _wf_load_state(workflow_id: str, instance_id: str) -> dict:
    """Load workflow instance state from disk, or return empty dict."""
    p = _wf_state_path(workflow_id, instance_id)
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return {}


def _wf_save_state(workflow_id: str, instance_id: str, data: dict):
    """Persist workflow instance state to disk.

    Strips transient provider cache/binding keys before writing.
    """
    p = _wf_state_path(workflow_id, instance_id)
    clean = {k: v for k, v in data.items()
             if not k.startswith("_provider_")}
    with open(p, "w") as f:
        json.dump(clean, f, indent=2)


def _wf_list_instances(workflow_id: str) -> list[dict]:
    """List all instances of a workflow type with summary info."""
    d = _WORKFLOW_STATE_DIR / workflow_id
    if not d.is_dir():
        return []
    instances = []
    for f in sorted(d.glob("*.state.json")):
        inst_id = f.stem.replace(".state", "")
        try:
            state = json.loads(f.read_text())
            node = state.get("node", "?")
        except Exception:
            node = "?"
        instances.append({
            "id": inst_id,
            "node": node,
            "mtime": f.stat().st_mtime,
        })
    # Sort newest first
    instances.sort(key=lambda x: x["mtime"], reverse=True)
    return instances


def _wf_notify(workflow_id: str, instance_id: str, event: dict):
    """Push event to all SSE observers for a workflow instance."""
    ck = _cache_key(workflow_id, instance_id)
    event.setdefault("timestamp", _time.time())
    dead = []
    for q in _workflow_observers.get(ck, []):
        try:
            q.put_nowait(event)
        except Exception:
            dead.append(q)
    for q in dead:
        _workflow_observers[ck].remove(q)


_portal_observers: list[Queue] = []


def _wf_notify_portal(event: dict):
    """Push event to all SSE observers of the portal page."""
    event.setdefault("timestamp", _time.time())
    dead = []
    for q in _portal_observers:
        try:
            q.put_nowait(event)
        except Exception:
            dead.append(q)
    for q in dead:
        _portal_observers.remove(q)


def _all_affordances(page: dict) -> list[dict]:
    """Collect all affordances: top-level + inline (fields, table, columns, properties)."""
    affs = list(page.get("affordances", []))
    st = page.get("state") or {}
    # Field affordances
    for field in (st.get("fields") or {}).values():
        fa = field.get("affordance") if isinstance(field, dict) else None
        if fa is not None:
            affs.append(fa)
    # Table affordances
    table = st.get("table")
    if isinstance(table, dict):
        affs.extend(table.get("affordances", []))
        for col in table.get("columns", []):
            if isinstance(col, dict):
                affs.extend(col.get("affordances", []))
        props = table.get("properties")
        if isinstance(props, dict):
            affs.extend(props.get("affordances", []))
    return affs


def _compute_feedback(before: dict, after: dict, acted_label: str = None) -> dict:
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

    before_aff = {_aff_key(a): a for a in _all_affordances(before)}
    new_affordances = []
    modified_affordances = []
    for a in _all_affordances(after):
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


# -- Workflow registry --
# Each entry maps a workflow_id to its handler module and display metadata.

_ALL_RENDERERS = ["raw", "light"]
_CUSTOM_WORKFLOWS_DIR = DATA_DIR / "custom_workflows"
_CUSTOM_WORKFLOWS_DIR.mkdir(exist_ok=True)


def _register_providers():
    """Register external state providers."""
    from engine.runtime.providers import registry
    from engine.runtime.test_provider import CounterProvider
    registry.register(CounterProvider())


def _discover_workflows():
    """Build the workflow registry from YAML definitions + builder handler."""
    _register_providers()
    workflows = {}

    # Built-in YAML workflows — loaded via the unified runtime
    _BUILTIN_YAMLS = {
        "create-cr": {
            "path": DATA_DIR / "agent_create_cr.yaml",
            "description": "Author a Change Record through the full pre-approval lifecycle.",
        },
        "create-executable-table": {
            "path": DATA_DIR / "agent_create_executable_table.yaml",
            "description": "Build a structured table with typed columns, acceptance criteria, and integrated execution.",
        },
    }
    for wf_id, info in _BUILTIN_YAMLS.items():
        try:
            defn = yaml.safe_load(info["path"].read_text())
            handler = WorkflowRuntime(defn)
            workflows[wf_id] = {
                "handler": handler,
                "title": handler.WORKFLOW_TITLE,
                "description": info["description"],
                "renderers": _ALL_RENDERERS,
            }
        except Exception as e:
            print(f"Warning: Failed to load {wf_id}: {e}")

    # Builder handler (special case — not YAML-driven)
    workflows["create-workflow"] = {
        "handler": builder_handler,
        "title": builder_handler.WORKFLOW_TITLE,
        "description": "Design a new workflow that agents can run without writing code.",
        "renderers": _ALL_RENDERERS,
    }

    # Discover custom workflows from YAML definitions
    for yaml_path in sorted(_CUSTOM_WORKFLOWS_DIR.glob("*.yaml")):
        try:
            defn = yaml.safe_load(yaml_path.read_text())
            wf_id = yaml_path.stem
            handler = WorkflowRuntime(defn)
            workflows[wf_id] = {
                "handler": handler,
                "title": handler.WORKFLOW_TITLE,
                "description": defn.get("workflow_description", ""),
                "renderers": _ALL_RENDERERS,
            }
        except Exception:
            pass  # skip malformed YAMLs silently

    return workflows


_WORKFLOWS = _discover_workflows()


def _migrate_legacy_state_files():
    """Migrate old flat state files to instance directories.

    Old format: data/workflows/{workflow_id}.state.json
    New format: data/workflows/{workflow_id}/{instance_id}.state.json
    """
    for f in list(_WORKFLOW_STATE_DIR.glob("*.state.json")):
        wf_id = f.name.replace(".state.json", "")
        if wf_id in _WORKFLOWS:
            dest_dir = _WORKFLOW_STATE_DIR / wf_id
            dest_dir.mkdir(exist_ok=True)
            inst_id = _wf_new_instance_id()
            f.rename(dest_dir / f"{inst_id}.state.json")


_migrate_legacy_state_files()


def _get_handler(workflow_id):
    """Return the handler module for a workflow, or None."""
    wf = _WORKFLOWS.get(workflow_id)
    return wf["handler"] if wf else None


def _render_agent_node(workflow_id: str, instance_id: str):
    """Render the current state of a workflow instance."""
    handler = _get_handler(workflow_id)
    if handler is None:
        return {"error": f"Unknown workflow: {workflow_id}"}
    data = _wf_load_state(workflow_id, instance_id)
    if not data or "node" not in data:
        data = handler.default_data()
        _wf_save_state(workflow_id, instance_id, data)
    return handler.render_node(data, workflow_id, instance_id)


def _process_agent_action(workflow_id: str, instance_id: str, body):
    """Process a POST action for a workflow instance."""
    handler = _get_handler(workflow_id)
    if handler is None:
        return {"error": f"Unknown workflow: {workflow_id}"}

    data = _wf_load_state(workflow_id, instance_id)
    if not data or "node" not in data:
        data = handler.default_data()
    result = handler.process_action(data, workflow_id, body, instance_id)
    if "error" not in result:
        _wf_save_state(workflow_id, instance_id, data)
    return result


def _wants_json() -> bool:
    """True when the client prefers JSON or hasn't specified a preference.

    /agent/ routes default to JSON (for agents). Browsers sending an explicit
    text/html Accept header still get HTML.
    """
    best = request.accept_mimetypes.best
    return best in ("application/json", None, "*/*", "")


def _render_portal() -> dict:
    """Build the portal's canonical {state, instructions, affordances} dict."""
    workflows = []
    affordances = []
    n = 1
    for wf_id, wf_info in _WORKFLOWS.items():
        instances = _wf_list_instances(wf_id)
        wf_entry = {
            "id": wf_id,
            "title": wf_info["title"],
            "description": wf_info["description"],
            "instances": [],
        }
        for inst in instances:
            wf_entry["instances"].append({
                "id": inst["id"],
                "node": inst["node"],
                "url": f"/agent/{wf_id}/{inst['id']}",
            })
            affordances.append({
                "id": n,
                "label": f"Open {wf_info['title']} ({inst['id']}: {inst['node']})",
                "method": "GET",
                "url": f"/agent/{wf_id}/{inst['id']}",
            })
            n += 1
            affordances.append({
                "id": n,
                "label": f"Delete {wf_info['title']} ({inst['id']})",
                "method": "POST",
                "url": f"/agent/{wf_id}/{inst['id']}/delete",
                "body": {},
            })
            n += 1
        affordances.append({
            "id": n,
            "label": f"New {wf_info['title']} instance",
            "method": "POST",
            "url": f"/agent/{wf_id}/new",
            "body": {},
        })
        n += 1
        workflows.append(wf_entry)

    return {
        "state": {
            "page": "agent",
            "page_title": "Agent Portal",
            "workflows": workflows,
        },
        "instructions": "Available workflows. Create new instances or open existing ones.",
        "affordances": affordances,
    }


@app.route("/agent")
def agent_portal():
    portal = _render_portal()
    # JSON for agents, HTML for browsers
    if _wants_json():
        return jsonify(portal)

    return render_template("agent.html", active_page="agent",
                           payload=portal,
                           payload_json=json.dumps(portal),
                           stream_url="/agent/stream",
                           show_raw_toggle=True)


@app.route("/agent/stream")
def agent_portal_stream():
    """SSE stream for the portal page — instance create/delete events."""
    def generate():
        q = Queue()
        _portal_observers.append(q)
        try:
            init = {
                "type": "init",
                "page": _render_portal(),
            }
            yield f"data: {json.dumps(init)}\n\n"
            while True:
                try:
                    event = q.get(timeout=15)
                    # On any change, send the full refreshed portal state
                    event["page"] = _render_portal()
                    yield f"data: {json.dumps(event)}\n\n"
                except Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            if q in _portal_observers:
                _portal_observers.remove(q)
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/agent/<workflow_id>/new", methods=["POST"])
def agent_new_instance(workflow_id):
    """Create a new workflow instance."""
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": "Unknown workflow"}), 404
    inst_id = _wf_new_instance_id()
    handler = _get_handler(workflow_id)
    data = handler.default_data()
    _wf_save_state(workflow_id, inst_id, data)
    # Notify portal observers
    _wf_notify_portal({"type": "instance_created", "workflow_id": workflow_id, "instance_id": inst_id})
    # Return confirmation — stay on portal
    if _wants_json():
        return jsonify({"instance_id": inst_id, "workflow_id": workflow_id}), 201
    return redirect("/agent")


@app.route("/agent/<workflow_id>/<instance_id>/observe")
def agent_observe(workflow_id, instance_id):
    if workflow_id not in _WORKFLOWS:
        abort(404)
    wf_info = _WORKFLOWS[workflow_id]
    return render_template(
        "agent_observer.html",
        active_page="agent",
        workflow_id=workflow_id,
        instance_id=instance_id,
        workflow_title=wf_info["title"],
        stream_url=f"/agent/{workflow_id}/{instance_id}/stream",
        renderers=json.dumps(wf_info["renderers"]),
    )


@app.route("/agent/<workflow_id>/<instance_id>/stream")
def agent_stream(workflow_id, instance_id):
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": "Unknown workflow"}), 404
    ck = _cache_key(workflow_id, instance_id)

    def generate():
        q = Queue()
        observers = _workflow_observers.setdefault(ck, [])
        observers.append(q)
        try:
            page = _render_agent_node(workflow_id, instance_id)
            init = {
                "type": "init",
                "current_path": _workflow_current_path.get(ck),
                "page": page,
                "last_feedback": _workflow_last_feedback.get(ck),
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
            if q in _workflow_observers.get(ck, []):
                _workflow_observers[ck].remove(q)
    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/agent/<workflow_id>/<instance_id>/delete", methods=["POST"])
def agent_delete(workflow_id, instance_id):
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": "Unknown workflow"}), 404
    p = _wf_state_path(workflow_id, instance_id)
    if p.exists():
        p.unlink()
    ck = _cache_key(workflow_id, instance_id)
    _workflow_current_path.pop(ck, None)
    _workflow_last_feedback.pop(ck, None)
    _wf_notify_portal({"type": "instance_deleted", "workflow_id": workflow_id, "instance_id": instance_id})
    return jsonify({"message": f"Instance '{instance_id}' of '{workflow_id}' deleted."})


@app.route("/agent/<workflow_id>/<instance_id>", methods=["GET"])
def agent_workflow_get(workflow_id, instance_id):
    if workflow_id not in _WORKFLOWS:
        if _wants_json():
            return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
        abort(404)
    ck = _cache_key(workflow_id, instance_id)
    page = _render_agent_node(workflow_id, instance_id)
    if page is None:
        if _wants_json():
            return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
        abort(404)
    node = (page.get("state") or {}).get("node") or (page.get("state") or {}).get("position") or workflow_id
    _workflow_current_path[ck] = node
    _wf_notify(workflow_id, instance_id, {"type": "navigate", "path": node, "content": json.dumps(page)})

    # JSON for agents, HTML observer for browsers
    if _wants_json():
        return jsonify(page)
    wf_info = _WORKFLOWS[workflow_id]
    return render_template(
        "agent_observer.html",
        active_page="agent",
        workflow_id=workflow_id,
        instance_id=instance_id,
        workflow_title=wf_info["title"],
        stream_url=f"/agent/{workflow_id}/{instance_id}/stream",
        renderers=json.dumps(wf_info["renderers"]),
    )


def _execute_and_feedback(workflow_id, instance_id, internal_body, acted_label=None):
    """Execute an agent action, compute feedback, notify observers.

    Returns (feedback_dict, http_status_code).
    """
    ck = _cache_key(workflow_id, instance_id)
    attempted = acted_label or internal_body.get("action", "?")
    before_full = _render_agent_node(workflow_id, instance_id)
    _wf_notify(workflow_id, instance_id, {"type": "action", "path": workflow_id, "body": internal_body})
    result = _process_agent_action(workflow_id, instance_id, internal_body)

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
        _workflow_last_feedback[ck] = feedback
        _wf_notify(workflow_id, instance_id, {"type": "result", "path": workflow_id, "result": before_full, "feedback": feedback})
        return feedback, 422

    after_full = result
    feedback = _compute_feedback(before_full, after_full, acted_label=acted_label)
    feedback["attempted_action"] = attempted

    node = (after_full.get("state") or {}).get("node") or (after_full.get("state") or {}).get("position") or workflow_id
    _workflow_current_path[ck] = node
    _workflow_last_feedback[ck] = feedback
    _wf_notify(workflow_id, instance_id, {"type": "result", "path": workflow_id, "result": after_full, "feedback": feedback})

    return feedback, 200


@app.route("/agent/<workflow_id>/<instance_id>/<resource>", methods=["POST"])
def agent_resource_post(workflow_id, instance_id, resource):
    """Resource-oriented endpoint — each affordance is a literal URL."""
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
    body = request.get_json(silent=True) or {}

    handler = _get_handler(workflow_id)
    resolved = handler.resolve_resource(resource, body)
    if resolved is None:
        return jsonify({"error": f"Unknown resource: {resource}"}), 404
    internal_body, acted_label = resolved

    feedback, status = _execute_and_feedback(workflow_id, instance_id,
                                             internal_body,
                                             acted_label=acted_label)
    return jsonify(feedback), status


@app.route("/agent/<workflow_id>/<instance_id>", methods=["POST"])
def agent_workflow_post(workflow_id, instance_id):
    """Legacy single-endpoint dispatch (backward compatibility)."""
    if workflow_id not in _WORKFLOWS:
        return jsonify({"error": f"Unknown workflow: {workflow_id}"}), 404
    body = request.get_json(silent=True) or {}
    acted_label = body.get("action", "?")
    feedback, status = _execute_and_feedback(workflow_id, instance_id, body,
                                             acted_label=acted_label)
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


@app.route("/workshop")
def workshop():
    return render_template("workshop.html", active_page="workshop")


