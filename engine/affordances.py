"""Affordance — a description of an action that can be performed on a component.

Affordances are pure data. They describe what actions are available, with
what parameters, at what URL. They serialize to dicts that appear in the
component's JSON output.

Affordances do NOT render themselves. The component that produces them is
responsible for accounting for each one in its render_from_data() method.
The render_affordance_html() utility is available as a convenience for
components that don't need custom placement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape

# --- Inline button style constants (legacy, used by STYLE_ refs) ---
STYLE_CONFIRM = (
    "cursor: pointer; border: 1px solid #4a4; background: #efffef;"
    " width: 24px; height: 24px; font-size: 14px; padding: 0; color: #2a2;"
    " vertical-align: middle; box-sizing: content-box;"
)
STYLE_REMOVE = (
    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
    " width: 24px; height: 24px; font-size: 12px; padding: 0; color: #c00;"
    " vertical-align: middle; box-sizing: content-box;"
)
STYLE_ARROW = (
    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
    " width: 24px; height: 24px; font-size: 10px; padding: 0;"
    " vertical-align: middle; box-sizing: content-box;"
)

# --- CSS class constants (for render_inline_button) ---
CSS_CONFIRM = "c-btn-confirm"
CSS_REMOVE = "c-btn-remove"
CSS_ARROW = "c-btn-arrow"
BUTTON_GAP = (
    '<span style="display: inline-block; width: 24px; height: 24px;'
    ' border: 1px solid transparent; vertical-align: middle;"></span>'
)


def _body_attr(body: dict) -> str:
    """Produce an HTML-escaped data-c-body attribute value."""
    return escape(json.dumps(body))


def render_inline_button(url: str, body: dict, content: str, css_class: str) -> str:
    """Render a button that POSTs a JSON body via event delegation.

    The component controls the URL, body, and CSS class. The global
    delegation script (component.js) handles the fetch+swap cycle.
    """
    tooltip = f'{escape("POST " + url)} {escape(json.dumps(body))}'
    return (
        f'<button data-c-post="{escape(url)}" data-c-body="{_body_attr(body)}"'
        f' class="{css_class}"'
        f' title="{tooltip}">'
        f'{content}</button>'
    )


@dataclass
class Affordance:
    """A description of a possible action on a component.

    Affordances are data, not renderers. They serialize to dicts for
    agents and include render_hints for components that use the
    render_affordance_html() utility.
    """
    label: str
    method: str
    url: str
    body: dict = field(default_factory=dict)
    instruction: str | None = None

    def serialize(self) -> dict:
        result = {
            "label": self.label,
            "method": self.method,
            "url": self.url,
            "body": self.body,
            "render_hints": self._render_hints(),
        }
        if self.instruction:
            result["instruction"] = self.instruction
        return result

    def _render_hints(self) -> dict:
        """Subclasses override to provide rendering-specific data."""
        return {}


class SetValueAffordance(Affordance):
    def _render_hints(self) -> dict:
        return {"type": "text_input"}


class ConfirmAffordance(Affordance):
    def _render_hints(self) -> dict:
        return {"type": "button"}


class SimpleButtonAffordance(Affordance):
    def _render_hints(self) -> dict:
        return {"type": "button"}


class AddComponentAffordance(Affordance):
    """Affordance for adding a component to a mutable page.

    Carries a structured type_catalog that appears in the agent-facing
    JSON, giving agents a categorized reference of available types.
    """

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 type_catalog: dict | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.type_catalog = type_catalog or {}

    def serialize(self) -> dict:
        result = super().serialize()
        if self.type_catalog:
            result["type_catalog"] = self.type_catalog
        return result

    def _render_hints(self) -> dict:
        return {"type": "add_component"}


class AddConstraintAffordance(Affordance):
    """An affordance that adds an ordering constraint between two items."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 item_values: list[str] | None = None,
                 item_labels: dict[str, str] | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.item_values = item_values or []
        self.item_labels = item_labels or {}

    def _render_hints(self) -> dict:
        return {"type": "constraint_picker", "options": self.item_values,
                "labels": self.item_labels}


class CheckboxAffordance(Affordance):
    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None, items: dict[str, bool] | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.items = items or {}

    def _render_hints(self) -> dict:
        return {"type": "checkbox", "items": self.items}


# ---------------------------------------------------------------------------
# Utility for components — renders an affordance dict as HTML.
# Components may use this for simple cases or build custom HTML instead.
# Either way, the component must account for every affordance.
# ---------------------------------------------------------------------------

def render_affordance_html(aff: dict) -> str:
    """Render an affordance dict as interactive HTML. Marks it as rendered."""
    aff["_rendered"] = True
    hints = aff.get("render_hints", {})
    aff_type = hints.get("type", "")
    label = aff.get("label", "")
    method = aff.get("method", "POST")
    url = aff.get("url", "")
    body = aff.get("body", {})
    endpoint = f"{method} {url}"

    if aff_type == "text_input":
        return _render_text_input(label, url, endpoint)
    elif aff_type == "button":
        return _render_button(label, url, endpoint, body)
    elif aff_type == "checkbox":
        return _render_checkbox(url, endpoint, hints.get("items", {}))
    elif aff_type == "radio":
        return _render_radio(url, endpoint, hints.get("options", []), hints.get("current"))
    elif aff_type == "multi_field":
        return _render_multi_field(label, url, endpoint, hints.get("fields", []), hints.get("values", {}))
    elif aff_type == "text_input_add":
        return _render_text_input_add(label, url, endpoint, body, hints.get("placeholder", ""))
    elif aff_type == "inline_cell":
        return ""
    elif aff_type == "small_button":
        return _render_small_button(label, url, endpoint, body)
    elif aff_type == "number_input":
        return _render_number_input(label, url, endpoint, hints)
    elif aff_type == "date_input":
        return _render_date_input(label, url, endpoint, hints)
    elif aff_type == "toggle":
        return _render_toggle(label, url, endpoint, hints)
    elif aff_type == "range_input":
        return _render_range_input(label, url, endpoint, hints)
    elif aff_type == "textarea":
        return _render_textarea(label, url, endpoint, hints)
    elif aff_type == "rating":
        return _render_rating(label, url, endpoint, hints)
    elif aff_type == "kv_input_add":
        return _render_kv_add(label, url, endpoint, hints)
    elif aff_type == "disabled_button":
        return _render_disabled_button(label, hints.get("message", ""))
    elif aff_type == "constraint_picker":
        return _render_constraint_picker(label, url, endpoint, hints)
    else:
        # Fallback: check for fillable parameters in body
        param_keys = [k for k, v in body.items() if isinstance(v, str) and v.startswith("<")]
        if param_keys:
            return _render_parameterized(label, url, endpoint, body, param_keys)
        return _render_button(label, url, endpoint, body)



def _render_text_input(label: str, url: str, endpoint: str) -> str:
    body_template = {"value": ""}
    return (
        f'<form style="display: inline" data-c-submit="{escape(url)}">'
        f'<input name="value" type="text"'
        f' title="{escape(endpoint)} {escape(json.dumps(body_template))}" />'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps(body_template))}">'
        f'{escape(label)}</button>'
        f'</form>'
    )


def _render_button(label: str, url: str, endpoint: str, body: dict) -> str:
    return (
        f'<div style="margin: 4px 0;">'
        f'<button data-c-post="{escape(url)}" data-c-body="{_body_attr(body)}"'
        f' style="cursor: pointer; font-size: 12px; padding: 4px 10px;"'
        f' title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
        f'</div>'
    )


def _render_checkbox(url: str, endpoint: str, items: dict) -> str:
    parts = []
    for item_key, checked in items.items():
        checked_attr = " checked" if checked else ""
        toggle_body = {item_key: not checked}
        parts.append(
            f'<label style="display: block; cursor: pointer;">'
            f'<input type="checkbox"{checked_attr} autocomplete="off"'
            f' data-c-post="{escape(url)}"'
            f' data-c-body="{_body_attr({item_key: "__TOGGLE"})}"'
            f' data-c-toggle-key="{escape(item_key)}"'
            f' title="{escape(endpoint)} {escape(json.dumps(toggle_body))}"'
            f' /> {escape(item_key)}'
            f'</label>'
        )
    return "".join(parts)


def _render_radio(url: str, endpoint: str, options: list, current: str | None) -> str:
    html = '<div style="margin: 4px 0;">'
    for opt in options:
        checked = " checked" if opt == current else ""
        body = {"value": opt}
        html += (
            f'<label style="display: block; cursor: pointer; padding: 2px 0;">'
            f'<input type="radio" name="{escape(url)}"{checked}'
            f' data-c-post="{escape(url)}" data-c-body="{_body_attr(body)}"'
            f' title="{escape(endpoint)} {escape(json.dumps(body))}"'
            f' /> {escape(opt)}'
            f'</label>'
        )
    html += '</div>'
    return html


def _render_multi_field(label: str, url: str, endpoint: str, fields: list, values: dict) -> str:
    inputs = ""
    for fd in fields:
        current = values.get(fd["key"])
        display = escape(str(current)) if current is not None else ""
        fd_type = fd.get("type", "text")

        if fd_type == "choice":
            options = fd.get("options", [])
            select_opts = ""
            for opt in options:
                selected = " selected" if opt == current else ""
                select_opts += f'<option value="{escape(opt)}"{selected}>{escape(opt)}</option>'
            inputs += (
                f'<div style="margin: 4px 0;">'
                f'<label>{escape(fd["label"])}: '
                f'<select name="{escape(fd["key"])}">'
                f'<option value="">-- select --</option>'
                f'{select_opts}'
                f'</select></label>'
                f'</div>'
            )
        else:
            placeholder = fd.get("instruction") or ""
            inputs += (
                f'<div style="margin: 4px 0;">'
                f'<label>{escape(fd["label"])}: '
                f'<input name="{escape(fd["key"])}" type="text" value="{display}" '
                f'placeholder="{escape(placeholder)}" '
                f'style="width: 200px;" /></label>'
                f'</div>'
            )

    return (
        f'<form data-c-submit="{escape(url)}">'
        f'{inputs}'
        f'<button type="submit" title="{escape(endpoint)} {escape(json.dumps(values if values else {}))}">'
        f'{escape(label)}</button>'
        f'</form>'
    )


def _render_text_input_add(label: str, url: str, endpoint: str, body: dict, placeholder: str) -> str:
    fixed_parts = {}
    input_key = "v"
    for k, v in body.items():
        if isinstance(v, str) and v.startswith("<"):
            input_key = k
        else:
            fixed_parts[k] = v

    hidden_inputs = ""
    for k, v in fixed_parts.items():
        hidden_inputs += f'<input type="hidden" name="{escape(k)}" value="{escape(str(v))}" />'

    return (
        f'<form style="display: inline" data-c-submit="{escape(url)}">'
        f'{hidden_inputs}'
        f'<input name="{escape(input_key)}" type="text" placeholder="{escape(placeholder or input_key)}" style="width: 160px;" />'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
        f'</form>'
    )


def _render_parameterized(label: str, url: str, endpoint: str, body: dict, param_keys: list[str]) -> str:
    fixed_parts = {k: v for k, v in body.items() if k not in param_keys}

    hidden_inputs = ""
    for k, v in fixed_parts.items():
        hidden_inputs += f'<input type="hidden" name="{escape(k)}" value="{escape(str(v))}" />'

    inputs = ""
    for pk in param_keys:
        inputs += (
            f'<input name="{escape(pk)}" type="text" placeholder="{escape(pk)}"'
            f' style="width: 100px; margin-right: 4px;" />'
        )

    return (
        f'<div style="margin: 4px 0; padding: 4px 0; border-top: 1px solid #eee;">'
        f'<form style="margin: 0;" data-c-submit="{escape(url)}">'
        f'{hidden_inputs}'
        f'{inputs}'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
        f'</form>'
        f'</div>'
    )


def _render_small_button(label: str, url: str, endpoint: str, body: dict) -> str:
    return (
        f'<button data-c-post="{escape(url)}" data-c-body="{_body_attr(body)}"'
        f' style="margin: 1px; cursor: pointer; width: 28px; height: 28px; font-size: 11px;"'
        f' title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
    )


def _render_number_input(label: str, url: str, endpoint: str, hints: dict) -> str:
    return (
        f'<form data-c-submit="{escape(url)}">'
        f'<input name="value" type="text" inputmode="decimal" style="width: 120px;"'
        f' title="{escape(endpoint)}" />'
        f'<div style="margin-top: 4px;">'
        f'<button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": ""}))}">'
        f'{escape(label)}</button>'
        f'</div>'
        f'</form>'
    )


def _render_date_input(label: str, url: str, endpoint: str, hints: dict) -> str:
    input_type = "datetime-local" if hints.get("include_time") else "date"
    return (
        f'<form data-c-submit="{escape(url)}">'
        f'<input name="value" type="{input_type}"'
        f' title="{escape(endpoint)}" />'
        f'<div style="margin-top: 4px;">'
        f'<button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": ""}))}">'
        f'{escape(label)}</button>'
        f'</div>'
        f'</form>'
    )


def _render_toggle(label: str, url: str, endpoint: str, hints: dict) -> str:
    current = hints.get("current")
    true_label = escape(hints.get("true_label", "Yes"))
    false_label = escape(hints.get("false_label", "No"))
    true_style = "background: #2a2; color: white;" if current is True else ""
    false_style = "background: #c22; color: white;" if current is False else ""
    true_body = {"value": True}
    false_body = {"value": False}
    return (
        f'<div style="display: flex; gap: 4px; margin: 4px 0;">'
        f'<button data-c-post="{escape(url)}" data-c-body="{_body_attr(true_body)}"'
        f' style="cursor: pointer; padding: 4px 12px; {true_style}"'
        f' title="{escape(endpoint)} {escape(json.dumps(true_body))}">'
        f'{true_label}</button>'
        f'<button data-c-post="{escape(url)}" data-c-body="{_body_attr(false_body)}"'
        f' style="cursor: pointer; padding: 4px 12px; {false_style}"'
        f' title="{escape(endpoint)} {escape(json.dumps(false_body))}">'
        f'{false_label}</button>'
        f'</div>'
    )


def _render_range_input(label: str, url: str, endpoint: str, hints: dict) -> str:
    min_val = hints.get("min", 0)
    max_val = hints.get("max", 100)
    step = hints.get("step", 1)
    current = hints.get("current")
    default = current if current is not None else min_val
    return (
        f'<form style="margin: 4px 0;" data-c-submit="{escape(url)}">'
        f'<input type="hidden" name="__parse" value="value:float" />'
        f'<input name="value" type="range" min="{min_val}" max="{max_val}" step="{step}" value="{default}"'
        f' oninput="this.nextElementSibling.textContent=this.value"'
        f' style="width: 200px; vertical-align: middle;" />'
        f'<span style="margin-left: 8px;">{default}</span>'
        f'<div style="margin-top: 4px;">'
        f'<button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": default}))}">'
        f'{escape(label)}</button>'
        f'</div>'
        f'</form>'
    )


def _render_textarea(label: str, url: str, endpoint: str, hints: dict) -> str:
    max_attr = f' maxlength="{hints["max_length"]}"' if hints.get("max_length") else ""
    return (
        f'<form data-c-submit="{escape(url)}">'
        f'<textarea name="value" rows="5" style="width: 100%; box-sizing: border-box;"{max_attr}'
        f'></textarea>'
        f'<div style="margin-top: 4px;">'
        f'<button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": ""}))}">'
        f'{escape(label)}</button>'
        f'</div>'
        f'</form>'
    )


def _render_rating(label: str, url: str, endpoint: str, hints: dict) -> str:
    max_rating = hints.get("max", 5)
    current = hints.get("current")
    labels = hints.get("labels") or {}
    html = '<div style="display: flex; gap: 4px; margin: 4px 0;">'
    for i in range(1, max_rating + 1):
        active = "background: #f0a020; color: white; font-weight: bold;" if current is not None and i <= current else ""
        title_label = labels.get(str(i), labels.get(i, ""))
        title_suffix = f" ({title_label})" if title_label else ""
        body = {"value": i}
        html += (
            f'<button data-c-post="{escape(url)}" data-c-body="{_body_attr(body)}"'
            f' style="cursor: pointer; width: 32px; height: 32px; {active}"'
            f' title="{escape(endpoint)} {{value: {i}}}{escape(title_suffix)}">'
            f'{i}</button>'
        )
    html += '</div>'
    return html


def _render_kv_add(label: str, url: str, endpoint: str, hints: dict) -> str:
    key_label = escape(hints.get("key_label", "Key"))
    value_label = escape(hints.get("value_label", "Value"))
    return (
        f'<form style="display: inline" data-c-submit="{escape(url)}">'
        f'<input type="hidden" name="action" value="add" />'
        f'<input name="key" type="text" placeholder="{key_label}" style="width: 120px; margin-right: 4px;" />'
        f'<input name="value" type="text" placeholder="{value_label}" style="width: 160px; margin-right: 4px;" />'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps({"action": "add", "key": "", "value": ""}))}">'
        f'{escape(label)}</button>'
        f'</form>'
    )


def _render_disabled_button(label: str, message: str) -> str:
    html = (
        f'<div style="margin: 4px 0;">'
        f'<button disabled style="font-size: 12px; padding: 4px 10px; opacity: 0.5; cursor: not-allowed;">'
        f'{escape(label)}</button>'
    )
    if message:
        html += f' <span style="color: #888; font-size: 0.9em;">{escape(message)}</span>'
    html += '</div>'
    return html


def _render_constraint_picker(label: str, url: str, endpoint: str, hints: dict) -> str:
    options = hints.get("options", [])
    labels = hints.get("labels", {})
    opts_html = '<option value="">-- select --</option>'
    for opt in options:
        display = f'{escape(labels.get(opt, opt))} ({escape(opt)})' if opt in labels else escape(opt)
        opts_html += f'<option value="{escape(opt)}">{display}</option>'
    return (
        f'<div style="margin: 4px 0; padding: 4px 0; border-top: 1px solid #eee;">'
        f'<form style="margin: 0;" data-c-submit="{escape(url)}">'
        f'<input type="hidden" name="action" value="add_constraint" />'
        f'<select name="item">{opts_html}</select>'
        f' must follow '
        f'<select name="after">{opts_html}</select>'
        f' <button type="submit" title="{escape(endpoint)}">{escape(label)}</button>'
        f'</form>'
        f'</div>'
    )


