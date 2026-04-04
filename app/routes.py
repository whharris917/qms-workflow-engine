import json
import queue
from pathlib import Path

from flask import Blueprint, Response, render_template, request, jsonify, redirect
from markupsafe import Markup

from pages import discover_pages, bind_page
from app.registry import InstanceRegistry

bp = Blueprint("main", __name__)

DATA_DIR = Path("data")

# Seed registry — unbound definitions with no runtime state
seeds = discover_pages()

# Instance registry — tracks spawned page instances
registry = InstanceRegistry(DATA_DIR)

# Auto-migrate legacy data files whose seed key isn't already registered
for key, seed in seeds.items():
    if (DATA_DIR / f"{key}.json").exists() and registry.get_instance(key) is None:
        registry.create_instance(key, seed.label, force_id=key)

# SSE subscribers: {instance_id: [queue, ...]}
# Connection state only — knows nothing about eigenforms
subscribers: dict[str, list[queue.Queue]] = {}


def get_page(instance_id: str):
    """Resolve an instance to its seed, then bind a transient page."""
    info = registry.get_instance(instance_id)
    if info is None:
        return None
    seed = seeds.get(info["type"])
    if seed is None:
        return None
    return bind_page(seed, DATA_DIR, instance_id)


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
    seed_list = [{"key": k, "label": s.label} for k, s in seeds.items()]
    instances = registry.list_instances()
    instance_list = [
        {"id": iid, "type": info["type"], "label": info["label"],
         "created_at": info.get("created_at", "")}
        for iid, info in instances.items()
    ]
    if wants_html(request):
        return render_template("index.html", seeds=seed_list, instances=instance_list)
    return jsonify({"seeds": seed_list, "instances": instance_list})


@bp.route("/instances", methods=["POST"])
def create_instance():
    if request.is_json:
        body = request.json
    else:
        body = {"type": request.form.get("type"), "label": request.form.get("label")}
    type_key = body.get("type")
    label = body.get("label")
    if not type_key or type_key not in seeds:
        if wants_html(request):
            return "Unknown page type", 400
        return jsonify({"error": f"Unknown type: {type_key}"}), 400
    if not label:
        label = seeds[type_key].label
    instance_id = registry.create_instance(type_key, label)
    if wants_html(request):
        return redirect("/")
    return jsonify({"instance_id": instance_id, "type": type_key, "label": label}), 201


@bp.route("/instances/<instance_id>/delete", methods=["POST"])
def delete_instance(instance_id):
    success = registry.delete_instance(instance_id, DATA_DIR)
    if not success:
        if wants_html(request):
            return "Instance not found", 404
        return jsonify({"error": "Instance not found"}), 404
    if wants_html(request):
        return redirect("/")
    return jsonify({"deleted": instance_id})


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
                               instance_id=instance_id)
    return jsonify(pg.serialize())


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
def eigenform(instance_id, path):
    pg = get_page(instance_id)
    if pg is None:
        if wants_html(request):
            return "Not found", 404
        return jsonify({"error": f"Unknown instance: {instance_id}"}), 404

    if request.method == "GET":
        ef = pg.find_eigenform(path)
        if ef is None:
            if wants_html(request):
                return "Not found", 404
            return jsonify({"error": f"Unknown path: {path}"}), 404
        if wants_html(request):
            html = Markup(ef.render())
            return render_template("page.html", page_html=html, title=ef.label,
                                   instance_id=instance_id)
        return jsonify(ef.serialize())

    # POST — mutate
    result = pg.handle_action(path, request.json)
    if result is None:
        return jsonify({"error": f"Unknown path: {path}"}), 404
    notify_subscribers(instance_id, result)
    if wants_html(request):
        return Markup(pg.render())
    return jsonify(result)
