"""Shared Jinja2 environment for eigenform HTML templates.

Templates live in app/templates/eigenforms/. Eigenforms call
render_template() to produce HTML from their serialized state.

The environment is configured with autoescape=True by default.
Templates that embed child eigenform HTML use the |safe filter.
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "app" / "templates" / "eigenforms"

_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _render_affordance(aff: dict) -> Markup:
    """Render an affordance dict to HTML. Available in templates as render_aff()."""
    from engine.affordances import render_affordance_html
    return Markup(render_affordance_html(aff))


_env.globals["render_aff"] = _render_affordance
_env.globals["CSS_CONFIRM"] = "ef-btn-confirm"
_env.globals["CSS_REMOVE"] = "ef-btn-remove"
_env.globals["CSS_ARROW"] = "ef-btn-arrow"


def _render_inline_button(url: str, body: dict, content: str, style: str = "") -> Markup:
    """Render an inline button. Available in templates as render_btn()."""
    from engine.affordances import render_inline_button
    return Markup(render_inline_button(url, body, content, style))


def _render_dep_line(depends_on, url_prefix: str = "") -> Markup:
    """Render dependency line. Available in templates as render_dep_line()."""
    from engine.eigenform import render_dependency_line
    return Markup(render_dependency_line(depends_on, url_prefix))


_env.globals["render_btn"] = _render_inline_button
_env.globals["render_dep_line"] = _render_dep_line
_env.globals["BUTTON_GAP"] = '<span class="ef-btn-gap"></span>'


def _tojson_filter(value):
    """Jinja2 filter: serialize to JSON string."""
    import json
    return json.dumps(value)


_env.filters["tojson"] = _tojson_filter


_COLLAPSE_BLANK_LINES = re.compile(r'\n{3,}')


def render_template(template_name: str, **context) -> str:
    """Render a Jinja2 template with the given context."""
    html = _env.get_template(template_name).render(**context)
    return _COLLAPSE_BLANK_LINES.sub('\n\n', html)


def safe(html: str) -> Markup:
    """Mark a string as safe HTML (won't be auto-escaped in templates)."""
    return Markup(html)
