from pathlib import Path

from flask import Blueprint, render_template, request, jsonify
from markupsafe import Markup

from engine.eigenforms import TextForm
from engine.page import PageForm
from engine.store import Store

bp = Blueprint("main", __name__)

store = Store(Path("data/state.json"))

# Definitions — these are templates, not live instances
title_def = TextForm(key="title", label="Document Title", instruction="A short, descriptive title.")
purpose_def = TextForm(key="purpose", label="Purpose", instruction="What problem does this CR solve?")

# Each page gets its own bound copies via bind()
pages = {
    "1": PageForm(key="1", label="Page 1", eigenforms=[title_def, purpose_def])
            .bind(store=store, scope="1", url_prefix="/page/1"),
    "2": PageForm(key="2", label="Page 2", eigenforms=[title_def])
            .bind(store=store, scope="2", url_prefix="/page/2"),
    "3": PageForm(key="3", label="Page 3", eigenforms=[title_def])
            .bind(store=store, scope="3", url_prefix="/page/3"),
}


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
    return render_template("page.html", page_html=html)


@bp.route("/page/<page_id>/<key>", methods=["POST"])
def handle_action(page_id, key):
    pg = pages.get(page_id)
    if pg is None:
        return jsonify({"error": f"Unknown page: {page_id}"}), 404
    result = pg.handle_action(key, request.json)
    if result is None:
        return jsonify({"error": f"Unknown key: {key}"}), 404
    return jsonify(result)
