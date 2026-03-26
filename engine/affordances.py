"""Affordance — a single action that can be performed on an eigenform.

An affordance serializes to a dict containing everything needed to both
display it to an agent (label, method, url, body, instruction) and render
it as interactive HTML (render_hints). The standalone render_affordance_html()
function produces HTML purely from this serialized dict.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape


@dataclass
class Affordance:
    """A single action that can be performed on an eigenform."""
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
        return {"type": "button"}


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
# Standalone HTML renderer — pure function of the serialized affordance dict
# ---------------------------------------------------------------------------

def render_affordance_html(aff: dict) -> str:
    """Render an affordance dict as interactive HTML."""
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
    else:
        # Fallback: render as a generic button
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
        f'<button onclick="fetch(\'{url}\','
        f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
        f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
        f' style="margin: 1px; cursor: pointer; font-size: 12px; padding: 4px 10px;"'
        f' title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
    )


def _render_checkbox(url: str, endpoint: str, items: dict) -> str:
    parts = []
    for item_key, checked in items.items():
        checked_attr = " checked" if checked else ""
        parts.append(
            f'<label style="display: block; cursor: pointer;">'
            f'<input type="checkbox"{checked_attr} onchange="'
            f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify({{{item_key}:this.checked}})}}).then(()=>location.reload())"
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
            inputs += (
                f'<div style="margin: 4px 0;">'
                f'<label>{escape(fd["label"])}: '
                f'<input name="{escape(fd["key"])}" type="text" value="{display}" '
                f'placeholder="{escape(fd.get("instruction", ""))}" '
                f'style="width: 200px;" /></label>'
                f'</div>'
            )
        js_keys.append(fd["key"])

    js_build = "var b={};"
    for k in js_keys:
        js_build += f"b['{k}']=this.elements['{k}'].value;"

    return (
        f'<form onsubmit="'
        f"{js_build}"
        f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
        f'{inputs}'
        f'<button type="submit" title="{escape(endpoint)}">{escape(label)}</button>'
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

    return (
        f'<form style="display: inline" onsubmit="'
        f"{js_build}"
        f"fetch('{url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
        f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
        f'<input name="v" type="text" placeholder="{escape(placeholder or input_key)}" style="width: 160px;" />'
        f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps(body))}">'
        f'{escape(label)}</button>'
        f'</form>'
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
