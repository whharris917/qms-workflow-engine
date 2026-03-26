"""Affordance — a single action that can be performed on an eigenform.

Every affordance knows how to serialize itself to JSON and render itself
as interactive HTML. Subclasses that fail to implement render() will
raise NotImplementedError.
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
    _rendered: bool = field(default=False, init=False, repr=False)

    def serialize(self) -> dict:
        result = {
            "label": self.label,
            "method": self.method,
            "url": self.url,
            "body": self.body,
        }
        if self.instruction:
            result["instruction"] = self.instruction
        return result

    def render(self) -> str:
        """Render this affordance as interactive HTML.

        Sets _rendered flag, then delegates to render_html().
        Eigenform.render() checks that all affordances were rendered
        and raises if any were missed.
        """
        self._rendered = True
        return self.render_html()

    def render_html(self) -> str:
        """Produce the HTML for this affordance. Subclasses must implement."""
        raise NotImplementedError


class SetValueAffordance(Affordance):
    """An affordance that sets a single value via a text input."""

    def render_html(self) -> str:
        endpoint = f'{self.method} {self.url}'
        return (
            f'<form style="display: inline" onsubmit="fetch(\'{self.url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{value:this.elements.value.value}})}}); return false">'
            f'<input name="value" type="text" oninput="this.nextElementSibling.title='
            f"'{escape(endpoint)} '+JSON.stringify({{value:this.value}})"
            f'" />'
            f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": ""}))}">'
            f'{escape(self.label)}</button>'
            f'</form>'
        )


class SwitchTabAffordance(Affordance):
    """An affordance that switches the active tab."""

    def render_html(self) -> str:
        endpoint = f'{self.method} {self.url}'
        body_js = json.dumps(self.body).replace('"', '&quot;')
        return (
            f'<button onclick="fetch(\'{self.url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({body_js})}})"'
            f' style="margin-right: 4px; cursor: pointer;"'
            f' title="{escape(endpoint)} {escape(json.dumps(self.body))}">'
            f'{escape(self.label)}</button>'
        )


class ConfirmAffordance(Affordance):
    """An affordance that confirms an eigenform without changing its value."""

    def render_html(self) -> str:
        endpoint = f'{self.method} {self.url}'
        body_js = json.dumps(self.body).replace('"', '&quot;')
        return (
            f'<button onclick="fetch(\'{self.url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({body_js})}})"'
            f' style="margin: 2px; cursor: pointer; font-size: 12px; padding: 3px 8px;'
            f' background: #e8e8e8; border: 1px solid #aaa; border-radius: 3px;"'
            f' title="{escape(endpoint)} {escape(json.dumps(self.body))}">'
            f'{escape(self.label)}</button>'
        )


class SimpleButtonAffordance(Affordance):
    """An affordance that renders as a single button with a fixed body."""

    def render_html(self) -> str:
        endpoint = f'{self.method} {self.url}'
        body_js = json.dumps(self.body).replace('"', '&quot;')
        return (
            f'<button onclick="fetch(\'{self.url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({body_js})}}).then(()=>location.reload())"'
            f' style="margin: 1px; cursor: pointer; font-size: 12px; padding: 4px 10px;"'
            f' title="{escape(endpoint)} {escape(json.dumps(self.body))}">'
            f'{escape(self.label)}</button>'
        )


class CheckboxAffordance(Affordance):
    """An affordance that sets multiple boolean items. Renders as individual checkboxes."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None, items: dict[str, bool] | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.items = items or {}

    def render_html(self) -> str:
        endpoint = f'{self.method} {self.url}'
        parts = []
        for item_key, checked in self.items.items():
            checked_attr = " checked" if checked else ""
            parts.append(
                f'<label style="display: block; cursor: pointer;">'
                f'<input type="checkbox"{checked_attr} onchange="'
                f"fetch('{self.url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
                f"body:JSON.stringify({{{item_key}:this.checked}})}}).then(()=>location.reload())"
                f'" title="{escape(endpoint)} {escape(json.dumps({item_key: not checked}))}"'
                f' /> {escape(item_key)}'
                f'</label>'
            )
        return "".join(parts)
