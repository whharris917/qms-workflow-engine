"""Affordance — a description of an action that can be performed on an eigenform.

Affordances are pure data. They describe what actions are available, with
what parameters, at what URL. They serialize to dicts that appear in the
eigenform's JSON output.

Affordances do NOT render themselves. The eigenform that produces them is
responsible for accounting for each one in its render_from_data() method.
The render_affordance_html() utility is available as a convenience for
eigenforms that don't need custom placement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape

# --- Inline button style constants ---
STYLE_CONFIRM = (
    "cursor: pointer; border: 1px solid #4a4; background: #efffef;"
    " width: 24px; height: 24px; font-size: 14px; padding: 0; color: #2a2;"
)
STYLE_REMOVE = (
    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
    " width: 24px; height: 24px; font-size: 12px; padding: 0; color: #c00;"
)
STYLE_ARROW = (
    "cursor: pointer; border: 1px solid #ccc; background: #f8f8f8;"
    " width: 24px; height: 24px; font-size: 10px; padding: 0;"
)


def render_inline_button(url: str, body: dict, content: str, style: str) -> str:
    """Render a button that POSTs a JSON body and reloads the page.

    Generates the fetch() JS, JSON-escaped body, and endpoint tooltip
    automatically. Use for inline action buttons (remove, move, etc.).
    """
    body_js = json.dumps(body).replace('"', '&quot;')
    endpoint = f'POST {url}'
    tooltip = f'{escape(endpoint)} {escape(json.dumps(body))}'
    return (
        f'<button onclick="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
        f' style="{style}"'
        f' title="{tooltip}">'
        f'{content}</button>'
    )


@dataclass
class Affordance:
    """A description of a possible action on an eigenform.

    Affordances are data, not renderers. They serialize to dicts for
    agents and include render_hints for eigenforms that use the
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


class SwitchTabAffordance(Affordance):
    def _render_hints(self) -> dict:
        return {"type": "tab_button"}


class ConfirmAffordance(Affordance):
    def _render_hints(self) -> dict:
        return {"type": "button"}


class SimpleButtonAffordance(Affordance):
    def _render_hints(self) -> dict:
        return {"type": "button"}


class CheckboxAffordance(Affordance):
    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None, items: dict[str, bool] | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.items = items or {}

    def _render_hints(self) -> dict:
        return {"type": "checkbox", "items": self.items}


# ---------------------------------------------------------------------------
# Utility for eigenforms — renders an affordance dict as HTML.
# Eigenforms may use this for simple cases or build custom HTML instead.
# Either way, the eigenform must account for every affordance.
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
    elif aff_type == "tab_button":
        return _render_tab_button(label, url, endpoint, body)
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
    elif aff_type == "accordion_toggle":
        return _render_accordion_toggle(label, url, endpoint, body, hints)
    elif aff_type == "disabled_button":
        return _render_disabled_button(label, hints.get("message", ""))
    else:
        # Fallback: check for fillable parameters in body
        param_keys = [k for k, v in body.items() if isinstance(v, str) and v.startswith("<")]
        if param_keys:
            return _render_parameterized(label, url, endpoint, body, param_keys)
        return _render_button(label, url, endpoint, body)


def _render_text_input(label: str, url: str, endpoint: str) -> str:
    return (
        f'<form style="display: inline" onsubmit="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({{value:this.elements.value.value}})}}); return false">'
        f'<input name="value" type="text" oninput="this.nextElementSibling.title='
        f"'{escape(endpoint)} '+JSON.stringify({{value:this.value}})"
        f'" />'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": ""}))}">'
        f'{escape(label)}</button>'
        f'</form>'
    )


def _render_button(label: str, url: str, endpoint: str, body: dict) -> str:
    body_js = json.dumps(body).replace('"', '&quot;')
    return (
        f'<div style="margin: 4px 0;">'
        f'<button onclick="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
        f' style="cursor: pointer; font-size: 12px; padding: 4px 10px;"'
        f' title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
        f'</div>'
    )


def _render_checkbox(url: str, endpoint: str, items: dict) -> str:
    parts = []
    for item_key, checked in items.items():
        checked_attr = " checked" if checked else ""
        key_escaped = item_key.replace("\\", "\\\\").replace("'", "\\'")
        parts.append(
            f'<label style="display: block; cursor: pointer;">'
            f'<input type="checkbox"{checked_attr} autocomplete="off" onchange="'
            f"var b={{}};b['{key_escaped}']=this.checked;"
            f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify(b)}}).then(()=>location.reload())"
            f'" title="{escape(endpoint)} {escape(json.dumps({item_key: not checked}))}"'
            f' /> {escape(item_key)}'
            f'</label>'
        )
    return "".join(parts)


def _render_radio(url: str, endpoint: str, options: list, current: str | None) -> str:
    html = '<div style="margin: 4px 0;">'
    for opt in options:
        checked = " checked" if opt == current else ""
        html += (
            f'<label style="display: block; cursor: pointer; padding: 2px 0;">'
            f'<input type="radio" name="{escape(url)}"{checked} onchange="'
            f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify({{value:'{escape(opt)}'}})}}).then(()=>location.reload())"
            f'" title="{escape(endpoint)} {escape(json.dumps({"value": opt}))}"'
            f' /> {escape(opt)}'
            f'</label>'
        )
    html += '</div>'
    return html


def _render_multi_field(label: str, url: str, endpoint: str, fields: list, values: dict) -> str:
    js_keys = []

    # Tooltip updater: rebuild body from all fields, update button title
    def make_tooltip_js():
        js = "var f=this.form;var b={};"
        for k in js_keys:
            js += f"b['{k}']=f.elements['{k}'].value;"
        js += f"f.querySelector('button[type=submit]').title='{escape(endpoint)} '+JSON.stringify(b)"
        return js

    inputs = ""
    for fd in fields:
        current = values.get(fd["key"])
        display = escape(str(current)) if current is not None else ""
        fd_type = fd.get("type", "text")
        js_keys.append(fd["key"])

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

    js_build = "var b={};"
    for k in js_keys:
        js_build += f"b['{k}']=this.elements['{k}'].value;"

    # Add oninput/onchange to each input/select after we know all keys
    tooltip_js = make_tooltip_js()
    inputs = inputs.replace('<input name=', f'<input oninput="{tooltip_js}" name=')
    inputs = inputs.replace('<select name=', f'<select onchange="{tooltip_js}" name=')

    return (
        f'<form onsubmit="'
        f"{js_build}"
        f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
        f'{inputs}'
        f'<button type="submit" title="{escape(endpoint)} {escape(json.dumps(values if values else {}))}">'
        f'{escape(label)}</button>'
        f'</form>'
    )


def _render_text_input_add(label: str, url: str, endpoint: str, body: dict, placeholder: str) -> str:
    # Determine the action and input key from the body template
    fixed_parts = {}
    input_key = "v"
    for k, v in body.items():
        if isinstance(v, str) and v.startswith("<"):
            input_key = k
        else:
            fixed_parts[k] = v

    js_build = "var b={};"
    for k, v in fixed_parts.items():
        js_build += f"b['{k}']='{v}';"
    js_build += f"b['{input_key}']=this.elements.v.value;"

    # Build the oninput tooltip updater using the same body construction
    js_tooltip = "var b={};"
    for k, v in fixed_parts.items():
        js_tooltip += f"b['{k}']='{v}';"
    js_tooltip += f"b['{input_key}']=this.value;"
    js_tooltip += f"this.form.querySelector('button[type=submit]').title='{escape(endpoint)} '+JSON.stringify(b)"

    return (
        f'<form style="display: inline" onsubmit="'
        f"{js_build}"
        f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
        f'<input name="v" type="text" placeholder="{escape(placeholder or input_key)}" style="width: 160px;"'
        f' oninput="{js_tooltip}" />'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
        f'</form>'
    )


def _render_parameterized(label: str, url: str, endpoint: str, body: dict, param_keys: list[str]) -> str:
    """Render an affordance with fillable parameters as a form with inputs."""
    fixed_parts = {k: v for k, v in body.items() if k not in param_keys}

    js_build = "var b={};"
    for k, v in fixed_parts.items():
        js_build += f"b['{k}']='{v}';"
    for pk in param_keys:
        js_build += f"b['{pk}']=this.elements['{pk}'].value;"

    # oninput: rebuild body from all form fields, update button title
    js_tooltip = "var f=this.form;var b={};"
    for k, v in fixed_parts.items():
        js_tooltip += f"b['{k}']='{v}';"
    for pk in param_keys:
        js_tooltip += f"b['{pk}']=f.elements['{pk}'].value;"
    js_tooltip += f"f.querySelector('button[type=submit]').title='{escape(endpoint)} '+JSON.stringify(b)"

    inputs = ""
    for pk in param_keys:
        inputs += (
            f'<input name="{escape(pk)}" type="text" placeholder="{escape(pk)}"'
            f' style="width: 100px; margin-right: 4px;"'
            f' oninput="{js_tooltip}" />'
        )

    return (
        f'<div style="margin: 4px 0; padding: 4px 0; border-top: 1px solid #eee;">'
        f'<form style="margin: 0;" onsubmit="'
        f"{js_build}"
        f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
        f'{inputs}'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
        f'</form>'
        f'</div>'
    )


def _render_tab_button(label: str, url: str, endpoint: str, body: dict) -> str:
    body_js = json.dumps(body).replace('"', '&quot;')
    return (
        f'<button onclick="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
        f' style="cursor: pointer; font-size: 12px; padding: 2px 8px;"'
        f' title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
    )


def _render_small_button(label: str, url: str, endpoint: str, body: dict) -> str:
    body_js = json.dumps(body).replace('"', '&quot;')
    return (
        f'<button onclick="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
        f' style="margin: 1px; cursor: pointer; width: 28px; height: 28px; font-size: 11px;"'
        f' title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
    )


def _render_number_input(label: str, url: str, endpoint: str, hints: dict) -> str:
    return (
        f'<form style="display: inline" onsubmit="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({{value:this.elements.value.value}})}}).then(()=>location.reload()); return false">'
        f'<input name="value" type="text" inputmode="decimal" style="width: 120px;"'
        f' oninput="this.nextElementSibling.title='
        f"'{escape(endpoint)} '+JSON.stringify({{value:this.value}})"
        f'" />'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": ""}))}">'
        f'{escape(label)}</button>'
        f'</form>'
    )


def _render_date_input(label: str, url: str, endpoint: str, hints: dict) -> str:
    input_type = "datetime-local" if hints.get("include_time") else "date"
    return (
        f'<form style="display: inline" onsubmit="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({{value:this.elements.value.value}})}}).then(()=>location.reload()); return false">'
        f'<input name="value" type="{input_type}"'
        f' onchange="this.nextElementSibling.title='
        f"'{escape(endpoint)} '+JSON.stringify({{value:this.value}})"
        f'" />'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": ""}))}">'
        f'{escape(label)}</button>'
        f'</form>'
    )


def _render_toggle(label: str, url: str, endpoint: str, hints: dict) -> str:
    current = hints.get("current")
    true_label = escape(hints.get("true_label", "Yes"))
    false_label = escape(hints.get("false_label", "No"))
    true_style = "background: #2a2; color: white;" if current is True else ""
    false_style = "background: #c22; color: white;" if current is False else ""
    return (
        f'<div style="display: flex; gap: 4px; margin: 4px 0;">'
        f'<button onclick="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({{value:true}})}}).then(()=>location.reload())"'
        f' style="cursor: pointer; padding: 4px 12px; {true_style}"'
        f' title="{escape(endpoint)} {escape(json.dumps({"value": True}))}">'
        f'{true_label}</button>'
        f'<button onclick="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({{value:false}})}}).then(()=>location.reload())"'
        f' style="cursor: pointer; padding: 4px 12px; {false_style}"'
        f' title="{escape(endpoint)} {escape(json.dumps({"value": False}))}">'
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
        f'<form style="margin: 4px 0;" onsubmit="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({{value:parseFloat(this.elements.value.value)}})}}).then(()=>location.reload()); return false">'
        f'<input name="value" type="range" min="{min_val}" max="{max_val}" step="{step}" value="{default}"'
        f' oninput="this.nextElementSibling.textContent=this.value;'
        f"this.form.querySelector('button[type=submit]').title="
        f"'{escape(endpoint)} '+JSON.stringify({{value:parseFloat(this.value)}})"
        f'" style="width: 200px; vertical-align: middle;" />'
        f'<span style="margin-left: 8px;">{default}</span>'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": default}))}">'
        f'{escape(label)}</button>'
        f'</form>'
    )


def _render_textarea(label: str, url: str, endpoint: str, hints: dict) -> str:
    max_attr = f' maxlength="{hints["max_length"]}"' if hints.get("max_length") else ""
    return (
        f'<form onsubmit="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({{value:this.elements.value.value}})}}).then(()=>location.reload()); return false">'
        f'<textarea name="value" rows="5" style="width: 100%; box-sizing: border-box;"{max_attr}'
        f' oninput="this.form.querySelector(\'button[type=submit]\').title='
        f"'{escape(endpoint)} '+JSON.stringify({{value:this.value}})"
        f'"></textarea>'
        f'<button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": ""}))}">'
        f'{escape(label)}</button>'
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
        html += (
            f'<button onclick="fetch(\'{url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{value:{i}}})}}).then(()=>location.reload())"'
            f' style="cursor: pointer; width: 32px; height: 32px; {active}"'
            f' title="{escape(endpoint)} {{value: {i}}}{escape(title_suffix)}">'
            f'{i}</button>'
        )
    html += '</div>'
    return html


def _render_kv_add(label: str, url: str, endpoint: str, hints: dict) -> str:
    key_label = escape(hints.get("key_label", "Key"))
    value_label = escape(hints.get("value_label", "Value"))
    tooltip_js = (
        f"var f=this.form;"
        f"f.querySelector('button[type=submit]').title="
        f"'{escape(endpoint)} '+JSON.stringify({{action:'add',key:f.elements.k.value,value:f.elements.v.value}})"
    )
    return (
        f'<form style="display: inline" onsubmit="'
        f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify({{action:'add',key:this.elements.k.value,value:this.elements.v.value}})}}).then(()=>location.reload()); return false\">"
        f'<input name="k" type="text" placeholder="{key_label}" style="width: 120px; margin-right: 4px;"'
        f' oninput="{tooltip_js}" />'
        f'<input name="v" type="text" placeholder="{value_label}" style="width: 160px; margin-right: 4px;"'
        f' oninput="{tooltip_js}" />'
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


def _render_accordion_toggle(label: str, url: str, endpoint: str, body: dict, hints: dict) -> str:
    expanded = hints.get("expanded", True)
    arrow = "&#9660;" if expanded else "&#9654;"
    body_js = json.dumps(body).replace('"', '&quot;')
    return (
        f'<div onclick="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
        f' style="cursor: pointer; padding: 6px 8px; background: #eee; margin: 4px 0;'
        f' border-radius: 4px; font-weight: bold; user-select: none;"'
        f' title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{arrow} {escape(label)}</div>'
    )
