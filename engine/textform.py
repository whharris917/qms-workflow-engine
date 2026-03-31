from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape

from engine.affordances import Affordance, SetValueAffordance, STYLE_CONFIRM
from engine.bases import ScalarForm


@dataclass
class TextForm(ScalarForm):
    """Single free-form string input."""
    default: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.value is not None and self.value != ""

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "value": self.value if self.value is not None else self.default,
        }

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html

        if data.get("edit_mode"):
            return self._render_edit_mode(data)

        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        html += f'<p><strong>Value:</strong> {escape(str(data["value"]))}</p>'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        return html

    def _render_edit_mode(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        url = self.url
        label = data["label"]

        # Label as editable input — matches ListForm inline edit style
        set_label_body = json.dumps({"action": "set_label", "label": label})
        edit_tooltip = f'POST {url} {escape(set_label_body)}'
        html = (
            f'<form style="display: inline; margin: 0 0 4px 0;" onsubmit="fetch(\'{url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{action:\'set_label\',label:this.elements.v.value}})'
            f'}}).then(()=>location.reload()); return false">'
            f'<input name="v" type="text" value="{escape(label)}"'
            f' style="border: 1px solid #ddd; padding: 2px 4px; width: 200px;"'
            f' title="{edit_tooltip}" />'
            f' <button type="submit" style="{STYLE_CONFIRM}"'
            f' title="{edit_tooltip}">&#10003;</button>'
            f'</form>'
        )
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        # Mark "Set Label" as rendered (the inline form above handles it);
        # skip affordances already rendered by chrome (gear icon)
        for aff in data.get("affordances", []):
            if aff.get("_rendered"):
                continue
            if aff.get("body", {}).get("action") == "set_label":
                aff["_rendered"] = True
            else:
                html += render_affordance_html(aff)
        return html

    def get_affordances(self) -> list[Affordance]:
        return [
            SetValueAffordance(
                label=f"Set {self.effective_label}",
                method="POST",
                url=self.url,
                body={"value": "<value>"},
                instruction=f"Replace <value> with the desired {self.effective_label.lower()}.",
            )
        ]

    def _parse(self, body: dict):
        return body.get("value")
