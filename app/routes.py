import json
import queue
from pathlib import Path

from flask import Blueprint, Response, render_template, request, jsonify
from markupsafe import Markup

from pages import build_pages

bp = Blueprint("main", __name__)

pages = build_pages(data_dir=Path("data"))

# SSE subscribers: {page_key: [queue, ...]}
subscribers: dict[str, list[queue.Queue]] = {}


def wants_html(req) -> bool:
    """True if the client prefers HTML (i.e. a browser or HTMX request)."""
    if req.headers.get("HX-Request") == "true":
        return True
    best = req.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "text/html"


def notify_subscribers(page_key: str, data: dict):
    """Push an SSE event to all subscribers of a page."""
    if page_key not in subscribers:
        return
    message = f"data: {json.dumps(data)}\n\n"
    dead = []
    for q in subscribers[page_key]:
        try:
            q.put_nowait(message)
        except queue.Full:
            dead.append(q)
    for q in dead:
        subscribers[page_key].remove(q)


@bp.route("/")
def index():
    page_list = [{"key": k, "label": pg.label} for k, pg in pages.items()]
    return render_template("index.html", pages=page_list)


@bp.route("/pages/<page_key>", methods=["GET", "POST"])
def page(page_key):
    pg = pages.get(page_key)
    if pg is None:
        if wants_html(request):
            return "Not found", 404
        return jsonify({"error": f"Unknown page: {page_key}"}), 404
    agent_view = request.args.get("view") == "agent"
    if request.method == "POST":
        pg.handle(request.json)
        result = pg.serialize()
        notify_subscribers(page_key, result)
        if wants_html(request):
            html = pg.render_agent() if agent_view else pg.render()
            return Markup(html)
        return jsonify(result)
    if wants_html(request):
        html = pg.render_agent() if agent_view else pg.render()
        html = Markup(html)
        return render_template("page.html", page_html=html, title=pg.label, page_key=page_key)
    return jsonify(pg.serialize())


@bp.route("/pages/<page_key>/stream")
def page_stream(page_key):
    if page_key not in pages:
        return jsonify({"error": f"Unknown page: {page_key}"}), 404

    q = queue.Queue(maxsize=50)
    if page_key not in subscribers:
        subscribers[page_key] = []
    subscribers[page_key].append(q)

    def generate():
        try:
            while True:
                message = q.get()
                yield message
        except GeneratorExit:
            if page_key in subscribers and q in subscribers[page_key]:
                subscribers[page_key].remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.route("/pages/<page_key>/<path:path>", methods=["GET", "POST"])
def eigenform(page_key, path):
    pg = pages.get(page_key)
    if pg is None:
        if wants_html(request):
            return "Not found", 404
        return jsonify({"error": f"Unknown page: {page_key}"}), 404

    agent_view = request.args.get("view") == "agent"

    if request.method == "GET":
        ef = pg.find_eigenform(path)
        if ef is None:
            if wants_html(request):
                return "Not found", 404
            return jsonify({"error": f"Unknown path: {path}"}), 404
        if wants_html(request):
            html = Markup(ef.render_agent() if agent_view else ef.render())
            return render_template("page.html", page_html=html, title=ef.label, page_key=page_key)
        return jsonify(ef.serialize())

    # POST — mutate
    result = pg.handle_action(path, request.json)
    if result is None:
        return jsonify({"error": f"Unknown path: {path}"}), 404
    notify_subscribers(page_key, result)
    if wants_html(request):
        html = pg.render_agent() if agent_view else pg.render()
        return Markup(html)
    return jsonify(result)
