"""Shared Jinja2 environment for component HTML templates.

Templates live in app/templates/components/. Components call
render_template() to produce HTML from their serialized state.

The environment is configured with autoescape=True by default.
Templates that embed child component HTML use the |safe filter.
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from markupsafe import Markup

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "app" / "templates" / "components"

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
_env.globals["CSS_CONFIRM"] = "c-btn-confirm"
_env.globals["CSS_REMOVE"] = "c-btn-remove"
_env.globals["CSS_ARROW"] = "c-btn-arrow"


def _render_inline_button(url: str, body: dict, content: str, style: str = "") -> Markup:
    """Render an inline button. Available in templates as render_btn()."""
    from engine.affordances import render_inline_button
    return Markup(render_inline_button(url, body, content, style))


def _render_dep_line(depends_on, url_prefix: str = "") -> Markup:
    """Render dependency line. Available in templates as render_dep_line()."""
    from engine.component import render_dependency_line
    return Markup(render_dependency_line(depends_on, url_prefix))


_env.globals["render_btn"] = _render_inline_button
_env.globals["render_dep_line"] = _render_dep_line
_env.globals["BUTTON_GAP"] = '<span class="c-btn-gap"></span>'


def _tojson_filter(value):
    """Jinja2 filter: serialize to JSON string."""
    import json
    return json.dumps(value)


_env.filters["tojson"] = _tojson_filter


_COLLAPSE_BLANK_LINES = re.compile(r'\n{3,}')

# Active theme (None = default). Set per-request via set_theme().
_active_theme: str | None = None


def set_theme(theme: str | None):
    """Set the active theme for template resolution."""
    global _active_theme
    _active_theme = theme


def get_theme() -> str | None:
    """Return the active theme name, or None for default."""
    return _active_theme


def render_template(template_name: str, **context) -> str:
    """Render a Jinja2 template with the given context.

    If a theme is active, tries {theme}/{template_name} first,
    then falls back to {template_name} in the default directory.
    """
    if _active_theme:
        themed = f"{_active_theme}/{template_name}"
        try:
            html = _env.get_template(themed).render(**context)
            return _COLLAPSE_BLANK_LINES.sub('\n\n', html)
        except TemplateNotFound:
            pass
    html = _env.get_template(template_name).render(**context)
    return _COLLAPSE_BLANK_LINES.sub('\n\n', html)


def safe(html: str) -> Markup:
    """Mark a string as safe HTML (won't be auto-escaped in templates)."""
    return Markup(html)
