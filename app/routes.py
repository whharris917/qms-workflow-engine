import json
import queue
from pathlib import Path

from flask import Blueprint, Response, render_template, request, jsonify
from markupsafe import Markup

from engine.eigenforms import CheckboxForm, TextForm
from engine.page import PageForm
from engine.store import Store

bp = Blueprint("main", __name__)

store = Store(Path("data/state.json"))

# SSE subscribers: {page_id: [queue, ...]}
subscribers: dict[str, list[queue.Queue]] = {}

# Definitions — these are templates, not live instances
title_def = TextForm(key="title", label="Document Title", instruction="A short, descriptive title.")
purpose_def = TextForm(key="purpose", label="Purpose", instruction="What problem does this CR solve?")
impacts_def = CheckboxForm(
    key="impacts", label="Impact Areas", instruction="Select all that apply.",
    items=["code", "documentation", "tests", "infrastructure"],
)

# Each page gets its own bound copies via bind()
pages = {
    "1": PageForm(key="1", label="Page 1", eigenforms=[title_def, purpose_def, impacts_def])
            .bind(store=store, scope="1", url_prefix="/page/1"),
    "2": PageForm(key="2", label="Page 2", eigenforms=[title_def])
            .bind(store=store, scope="2", url_prefix="/page/2"),
    "3": PageForm(key="3", label="Page 3", eigenforms=[title_def])
            .bind(store=store, scope="3", url_prefix="/page/3"),
}


def notify_subscribers(page_id: str, data: dict):
    """Push an SSE event to all subscribers of a page."""
    if page_id not in subscribers:
        return
    message = f"data: {json.dumps(data)}\n\n"
    dead = []
    for q in subscribers[page_id]:
        try:
            q.put_nowait(message)
        except queue.Full:
            dead.append(q)
    for q in dead:
        subscribers[page_id].remove(q)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/page/<page_id>")
def page(page_id):
    pg = pages.get(page_id)
    if pg is None:
        return jsonify({"error": f"Unknown page: {page_id}"}), 404
    return jsonify(pg.serialize())


@bp.route("/page/<page_id>/view")
def page_view(page_id):
    pg = pages.get(page_id)
    if pg is None:
        return "Not found", 404
    html = Markup(pg.render())
    return render_template("page.html", page_html=html, title=pg.label, page_id=page_id)


@bp.route("/page/<page_id>/stream")
def page_stream(page_id):
    if page_id not in pages:
        return jsonify({"error": f"Unknown page: {page_id}"}), 404

    q = queue.Queue(maxsize=50)
    if page_id not in subscribers:
        subscribers[page_id] = []
    subscribers[page_id].append(q)

    def generate():
        try:
            while True:
                message = q.get()
                yield message
        except GeneratorExit:
            if page_id in subscribers and q in subscribers[page_id]:
                subscribers[page_id].remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@bp.route("/page/<page_id>/<key>", methods=["POST"])
def handle_action(page_id, key):
    pg = pages.get(page_id)
    if pg is None:
        return jsonify({"error": f"Unknown page: {page_id}"}), 404
    result = pg.handle_action(key, request.json)
    if result is None:
        return jsonify({"error": f"Unknown key: {key}"}), 404
    notify_subscribers(page_id, result)
    return jsonify(result)
