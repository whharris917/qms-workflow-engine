import json
import queue
from pathlib import Path

from flask import Blueprint, Response, render_template, request, jsonify
from markupsafe import Markup

from engine.chain import ChainForm
from engine.choice import ChoiceForm
from engine.eigenforms import CheckboxForm, TextForm
from engine.listform import ListForm
from engine.multi import FieldDescriptor, MultiForm
from engine.table import TableForm
from engine.rubiks import RubiksCubeForm
from engine.page import PageForm
from engine.tab import TabForm

bp = Blueprint("main", __name__)

DATA_DIR = Path("data")

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
            .bind(data_dir=DATA_DIR, scope="1", url_prefix="/page/1"),
    "2": PageForm(key="2", label="Page 2", instruction="Fill out each tab to complete the change request.", eigenforms=[
                TabForm(key="tabs", label="Details", tabs={
                    "basic": TextForm(key="title", label="Document Title", instruction="A short, descriptive title."),
                    "scope": TextForm(key="scope", label="Scope", instruction="What is affected by this change?"),
                    "impact": CheckboxForm(key="impacts", label="Impact Areas", instruction="Select all that apply.",
                                           items=["code", "documentation", "tests", "infrastructure"]),
                }),
            ]).bind(data_dir=DATA_DIR, scope="2", url_prefix="/page/2"),
    "4": PageForm(key="4", label="Page 4", instruction="Complete each step in sequence.", eigenforms=[
                ChainForm(key="chain", label="Change Request Wizard", instruction="Fill out each step to proceed.", steps=[
                    TextForm(key="title", label="Document Title", instruction="A short, descriptive title."),
                    TextForm(key="purpose", label="Purpose", instruction="What problem does this CR solve?"),
                    TextForm(key="scope", label="Scope", instruction="What is affected by this change?"),
                    CheckboxForm(key="impacts", label="Impact Areas", instruction="Select all that apply.",
                                 items=["code", "documentation", "tests", "infrastructure"]),
                ]),
            ]).bind(data_dir=DATA_DIR, scope="4", url_prefix="/page/4"),
    "6": PageForm(key="6", label="Page 6", instruction="A change request form showcasing ChoiceForm, ListForm, and MultiForm.", eigenforms=[
                MultiForm(key="basic_info", label="Basic Information",
                          instruction="Provide the core details for this change request.",
                          fields=[
                              FieldDescriptor(key="title", label="Title", instruction="Short descriptive title."),
                              FieldDescriptor(key="author", label="Author", instruction="Who is proposing this change?"),
                              FieldDescriptor(key="priority", label="Priority", type="choice",
                                              options=["Low", "Medium", "High", "Critical"]),
                          ]),
                ChoiceForm(key="change_type", label="Change Type",
                           instruction="What kind of change is this?",
                           options=["New Feature", "Bug Fix", "Refactor", "Documentation", "Infrastructure"]),
                CheckboxForm(key="affected_areas", label="Affected Areas",
                             instruction="Select all areas impacted by this change.",
                             items=["frontend", "backend", "database", "API", "CI/CD"]),
                ListForm(key="requirements", label="Requirements",
                         instruction="List the requirements for this change."),
                ListForm(key="risks", label="Risks",
                         instruction="List any risks or concerns."),
            ]).bind(data_dir=DATA_DIR, scope="6", url_prefix="/page/6"),
    "5": PageForm(key="5", label="Page 5", instruction="Build and populate a table.", eigenforms=[
                TableForm(key="table", label="Data Table",
                          instruction="Add columns, then rows, then fill in cells."),
            ]).bind(data_dir=DATA_DIR, scope="5", url_prefix="/page/5"),
    "3": PageForm(key="3", label="Page 3", eigenforms=[
                RubiksCubeForm(key="cube", label="Rubik's Cube",
                               instruction="A fully functional cube. Rotate any face."),
            ]).bind(data_dir=DATA_DIR, scope="3", url_prefix="/page/3"),
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
