import json
import queue
from pathlib import Path

from flask import Blueprint, Response, render_template, request, jsonify, redirect, abort
from markupsafe import Markup

from pages import discover_pages, bind_page
from app.registry import InstanceRegistry
from app.manual import build_manual_toc, render_md, render_md_file, QUALITY_MANUAL_DIR
from engine.templates import set_theme

bp = Blueprint("main", __name__)

DATA_DIR = Path("data")

# Instance registry — tracks spawned page instances
registry = InstanceRegistry(DATA_DIR)

# SSE subscribers: {instance_id: [queue, ...]}
# Connection state only — knows nothing about components
subscribers: dict[str, list[queue.Queue]] = {}


def seeds() -> dict:
    """Discover page seeds fresh on every call."""
    return discover_pages()


THEMES = {"default", "sleek"}
THEME_CSS = {"sleek": "sleek.css"}


@bp.before_request
def _apply_theme():
    theme = request.cookies.get("c-theme", "sleek")
    set_theme(theme if theme in THEMES and theme != "default" else None)


def _theme_css() -> str | None:
    """Return the CSS filename for the active theme, or None."""
    from engine.templates import get_theme
    theme = get_theme()
    return THEME_CSS.get(theme) if theme else None


def get_page(instance_id: str):
    """Resolve an instance to its seed, then bind a transient page."""
    info = registry.get_instance(instance_id)
    if info is None:
        return None
    seed = seeds().get(info["type"])
    if seed is None:
        return None
    return bind_page(seed, DATA_DIR, instance_id, label=info.get("label"))


def wants_html(req) -> bool:
    """True if the client prefers HTML (i.e. a browser request)."""
    best = req.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "text/html"


def notify_subscribers(instance_id: str, data: dict):
    """Push an SSE event to all subscribers of a page instance."""
    if instance_id not in subscribers:
        return
    message = f"data: {json.dumps(data)}\n\n"
    dead = []
    for q in subscribers[instance_id]:
        try:
            q.put_nowait(message)
        except queue.Full:
            dead.append(q)
    for q in dead:
        subscribers[instance_id].remove(q)


@bp.route("/")
def index():
    if wants_html(request):
        return render_template("home.html", active_page="home")
    # JSON clients get the seed/instance listing
    seed_list = [{"key": k, "label": s.label} for k, s in seeds().items()]
    instances = registry.list_instances()
    instance_list = [
        {"id": iid, "url": f"/pages/{iid}", "type": info["type"],
         "label": info["label"], "created_at": info.get("created_at", "")}
        for iid, info in instances.items()
    ]
    return jsonify({"seeds": seed_list, "instances": instance_list})


def _bind_deepdive():
    """Bind the deepdive seed to a fixed scope/url_prefix (not via the
    InstanceRegistry — this page has a permanent URL)."""
    seed = seeds().get("deepdive")
    if seed is None:
        return None
    return seed.bind(DATA_DIR, scope="deepdive", url_prefix="/deepdive")


@bp.route("/deepdive", methods=["GET", "POST"])
def deepdive():
    """Self-referential page: the engine analyzing itself."""
    pg = _bind_deepdive()
    if pg is None:
        return "Deep dive page seed not found.", 500
    if request.method == "POST":
        pg.handle(request.json)
        if wants_html(request):
            return Markup(pg.render())
        return jsonify(pg.serialize())
    if wants_html(request):
        html = Markup(pg.render())
        return render_template("page.html", page_html=html, title=pg.label,
                               instance_id="deepdive", theme_css=_theme_css(),
                               active_page="deepdive")
    return jsonify(pg.serialize())


@bp.route("/deepdive/<path:path>", methods=["GET", "POST"])
def deepdive_component(path):
    """Action/component routing for the deepdive page (tab switches, etc.)."""
    pg = _bind_deepdive()
    if pg is None:
        return "Not found", 404
    if request.method == "GET":
        ef = pg.find_component(path)
        if ef is None:
            return jsonify({"error": f"Unknown path: {path}"}), 404
        if wants_html(request):
            html = Markup(ef.render())
            return render_template("page.html", page_html=html, title=ef.label,
                                   instance_id="deepdive", theme_css=_theme_css(),
                                   active_page="deepdive")
        return jsonify(ef.serialize())
    result = pg.handle_action(path, request.json)
    if result is None:
        return jsonify({"error": f"Unknown path: {path}"}), 404
    if wants_html(request):
        return Markup(pg.render())
    ef = pg.find_component(path)
    if ef is not None:
        ef_state = ef.serialize()
        if "error" in result:
            ef_state["error"] = result["error"]
            ef_state["failed_action"] = result.get("failed_action")
        return jsonify(ef_state)
    return jsonify(result)


@bp.route("/framing")
def framing():
    """Conceptual framing: a design plan for sharpening the engine's vocabulary.

    Hand-rolled HTML — this page is prose with tables and diagrams, not an
    interactive form, so it bypasses the component engine entirely.
    """
    return render_template("framing.html", active_page="framing")


@bp.route("/wiki")
def wiki():
    """Hypothetical Wikipedia-style article about the engine."""
    return render_template("wiki.html", active_page="wiki")


# Learning Portal — progressive tutorial pages.
# Each lesson is a hand-rolled HTML template extending learn/_lesson_base.html.
# The slug maps to a template file under app/templates/learn/.
_LEARN_LESSONS = {
    # Fundamentals
    "hello":             "learn/lesson_1_hello.html",
    "loop":              "learn/lesson_2_loop.html",
    "data":              "learn/lesson_3_data.html",
    "compose":           "learn/lesson_4_compose.html",
    "humans-and-agents": "learn/lesson_5_humans_and_agents.html",
    # Deep dives
    "affordances":       "learn/lesson_6_affordances.html",
    "reconciliation":    "learn/lesson_7_reconciliation.html",
    "mutation":          "learn/lesson_8_mutation.html",
}


@bp.route("/learn")
def learn_index():
    """Learning Portal landing page — lesson grid + intro."""
    return render_template("learn.html", active_page="learn")


@bp.route("/learn/<slug>")
def learn_lesson(slug):
    """Individual lesson pages. Slug maps to a template file in learn/."""
    template = _LEARN_LESSONS.get(slug)
    if template is None:
        abort(404)
    return render_template(template, active_page="learn")


@bp.route("/portal")
def portal():
    instances = registry.list_instances()
    # Group instances by seed type for the card grid
    grouped = []
    for key, seed in seeds().items():
        seed_instances = [
            {"id": iid, "label": info["label"], "created_at": info.get("created_at", "")}
            for iid, info in instances.items()
            if info["type"] == key
        ]
        grouped.append({"key": key, "label": seed.label, "instances": seed_instances})
    if wants_html(request):
        return render_template("portal.html", grouped_seeds=grouped, active_page="portal")
    return jsonify({"seeds": [{"key": g["key"], "label": g["label"],
                                "instances": g["instances"]} for g in grouped]})


@bp.route("/instances", methods=["POST"])
def create_instance():
    if request.is_json:
        body = request.json
    else:
        body = {"type": request.form.get("type"), "label": request.form.get("label")}
    type_key = body.get("type")
    label = body.get("label")
    current_seeds = seeds()
    if not type_key or type_key not in current_seeds:
        if wants_html(request):
            return "Unknown page type", 400
        return jsonify({"error": f"Unknown type: {type_key}"}), 400
    if not label:
        label = current_seeds[type_key].label
    instance_id = registry.create_instance(type_key, label)
    if wants_html(request):
        return redirect("/portal")
    return jsonify({"instance_id": instance_id, "url": f"/pages/{instance_id}",
                    "type": type_key, "label": label}), 201


@bp.route("/instances/<instance_id>/delete", methods=["POST"])
def delete_instance(instance_id):
    success = registry.delete_instance(instance_id, DATA_DIR)
    if not success:
        if wants_html(request):
            return "Instance not found", 404
        return jsonify({"error": "Instance not found"}), 404
    if wants_html(request):
        return redirect("/portal")
    return jsonify({"deleted": instance_id})


@bp.route("/types")
def types():
    from engine.registry import describe_types
    return jsonify(describe_types())


@bp.route("/pages/<instance_id>", methods=["GET", "POST"])
def page(instance_id):
    pg = get_page(instance_id)
    if pg is None:
        if wants_html(request):
            return "Not found", 404
        return jsonify({"error": f"Unknown instance: {instance_id}"}), 404
    if request.method == "POST":
        pg.handle(request.json)
        result = pg.serialize()
        notify_subscribers(instance_id, result)
        if wants_html(request):
            return Markup(pg.render())
        return jsonify(result)
    if wants_html(request):
        html = Markup(pg.render())
        return render_template("page.html", page_html=html, title=pg.label,
                               instance_id=instance_id, theme_css=_theme_css(),
                               active_page="portal")
    if request.args.get("depth") == "shallow":
        return jsonify(_shallow_serialize(pg))
    return jsonify(pg.serialize())


def _shallow_serialize(pg) -> dict:
    """Produce a compact page summary: labels and completion status only."""
    return {
        "label": pg.label,
        "complete": pg.is_complete,
        "components": [
            {"label": ef.label, "complete": ef.is_complete}
            for ef in pg.components
        ],
    }


@bp.route("/pages/<instance_id>/stream")
def page_stream(instance_id):
    if registry.get_instance(instance_id) is None:
        return jsonify({"error": f"Unknown instance: {instance_id}"}), 404

    q = queue.Queue(maxsize=50)
    if instance_id not in subscribers:
        subscribers[instance_id] = []
    subscribers[instance_id].append(q)

    def generate():
        try:
            while True:
                message = q.get()
                yield message
        except GeneratorExit:
            if instance_id in subscribers and q in subscribers[instance_id]:
                subscribers[instance_id].remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.route("/pages/<instance_id>/<path:path>", methods=["GET", "POST"])
def component(instance_id, path):
    pg = get_page(instance_id)
    if pg is None:
        if wants_html(request):
            return "Not found", 404
        return jsonify({"error": f"Unknown instance: {instance_id}"}), 404

    if request.method == "GET":
        ef = pg.find_component(path)
        if ef is None:
            if wants_html(request):
                return "Not found", 404
            return jsonify({"error": f"Unknown path: {path}"}), 404
        if wants_html(request):
            html = Markup(ef.render())
            return render_template("page.html", page_html=html, title=ef.label,
                                   instance_id=instance_id, theme_css=_theme_css(),
                                   active_page="portal")
        return jsonify(ef.serialize())

    # POST — mutate
    result = pg.handle_action(path, request.json)
    if result is None:
        return jsonify({"error": f"Unknown path: {path}"}), 404
    notify_subscribers(instance_id, result)
    if wants_html(request):
        return Markup(pg.render())
    # Return just the targeted component state, not the full page
    ef = pg.find_component(path)
    if ef is not None:
        ef_state = ef.serialize()
        if "error" in result:
            ef_state["error"] = result["error"]
            ef_state["failed_action"] = result.get("failed_action")
        return jsonify(ef_state)
    return jsonify(result)


# ── Quality Manual ──

@bp.route("/manual")
def manual_index():
    toc = build_manual_toc()
    return render_template("manual_index.html", toc=toc, active_page="manual")


@bp.route("/manual/<path:slug>")
def manual_page(slug):
    file_path = QUALITY_MANUAL_DIR / f"{slug}.md"
    content = render_md(file_path, current_slug=slug)
    if content is None:
        abort(404)
    toc = build_manual_toc()
    title = file_path.stem.replace("-", " ").replace("_", " ")
    return render_template("manual_page.html", content=content, toc=toc,
                           page_title=title, current_slug=slug, active_page="manual")


# ── QMS Dashboard, Workspace, Inbox ──

def _list_crs() -> list[dict]:
    """List all CR data files, sorted by ID."""
    crs = []
    for p in sorted(DATA_DIR.glob("CR-*.json")):
        crs.append(json.loads(p.read_text(encoding="utf-8")))
    return crs


@bp.route("/qms")
def qms():
    return render_template("qms.html", crs=_list_crs(), active_page="qms")


@bp.route("/workspace")
def workspace():
    return render_template("workspace.html", crs=_list_crs(), active_page="workspace")


@bp.route("/inbox")
def inbox():
    return render_template("inbox.html", active_page="inbox")


# ── README ──

README_PATH = Path(__file__).resolve().parent.parent / "README.md"


@bp.route("/readme")
def readme():
    content = render_md_file(README_PATH)
    if content is None:
        abort(404)
    return render_template("readme.html", content=content, active_page="readme")
