"""WFE Web UI — minimal Flask application."""

import json
from pathlib import Path

import yaml
import markdown
from flask import Flask, render_template, abort, request, redirect, url_for, jsonify

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
    app.run(debug=True, port=5000)
