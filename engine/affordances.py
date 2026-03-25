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
    parameters: dict = field(default_factory=dict)

    def serialize(self) -> dict:
        return {
            "label": self.label,
            "method": self.method,
            "url": self.url,
            "parameters": self.parameters,
        }

    def render(self) -> str:
        """Render this affordance as interactive HTML."""
        raise NotImplementedError


class SetValueAffordance(Affordance):
    """An affordance that sets a single value via a text input."""

    def render(self) -> str:
        endpoint = f'{self.method} {self.url}'
        return (
            f'<form style="display: inline" onsubmit="fetch(\'{self.url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{value:this.elements.value.value}})}}).then(()=>location.reload());return false">'
            f'<input name="value" type="text" oninput="this.nextElementSibling.title='
            f"'{escape(endpoint)} '+JSON.stringify({{value:this.value}})"
            f'" />'
            f' <button type="submit" title="{escape(endpoint)} {escape(json.dumps({"value": ""}))}">'
            f'{escape(self.label)}</button>'
            f'</form>'
        )
