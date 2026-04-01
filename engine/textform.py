from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape

from engine.affordances import Affordance, SetValueAffordance, STYLE_CONFIRM
from engine.eigenform import Eigenform


@dataclass
class TextForm(Eigenform):
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
        instruction = data.get("instruction") or ""

        # Same shape as normal mode, but label and instruction are editable inputs.
        # Inputs use font:inherit and match the margins of the <h3>/<p> they replace.

        # Label — replaces <h3> (browser default: margin ~0.83em 0, font-size 1.17em, bold)
        label_body = json.dumps({"action": "set_label", "label": label})
        label_tooltip = f'POST {url} {escape(label_body)}'
        html = (
            f'<form style="display: flex; align-items: center; gap: 4px;'
            f' margin: 0.83em 0;" onsubmit="fetch(\'{url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{action:\'set_label\',label:this.elements.v.value}})'
            f'}}).then(()=>location.reload()); return false">'
            f'<input name="v" type="text" value="{escape(label)}"'
            f' style="font: inherit; font-size: 1.17em; font-weight: bold;'
            f' border: 1px solid #ddd; padding: 1px 3px; margin: 0;"'
            f' title="{label_tooltip}" />'
            f' <button type="submit" style="{STYLE_CONFIRM}"'
            f' title="{label_tooltip}">&#10003;</button>'
            f'</form>'
        )

        # Instruction — replaces <p> (browser default: margin 1em 0)
        instr_body = json.dumps({"action": "set_instruction", "instruction": instruction})
        instr_tooltip = f'POST {url} {escape(instr_body)}'
        html += (
            f'<form style="display: flex; align-items: center; gap: 4px;'
            f' margin: 1em 0;" onsubmit="fetch(\'{url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({{action:\'set_instruction\',instruction:this.elements.v.value}})'
            f'}}).then(()=>location.reload()); return false">'
            f'<input name="v" type="text" value="{escape(instruction)}"'
            f' placeholder="Instruction text"'
            f' style="font: inherit; border: 1px solid #ddd; padding: 1px 3px;'
            f' margin: 0; width: 100%;"'
            f' title="{instr_tooltip}" />'
            f' <button type="submit" style="{STYLE_CONFIRM}"'
            f' title="{instr_tooltip}">&#10003;</button>'
            f'</form>'
        )

        # Value — same as normal mode
        html += f'<p><strong>Value:</strong> {escape(str(data["value"]))}</p>'

        # Mark edit affordances as rendered (inline forms handle them)
        for aff in data.get("affordances", []):
            if aff.get("_rendered"):
                continue
            action = aff.get("body", {}).get("action")
            if action in ("set_label", "set_instruction"):
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

    def _handle(self, body: dict) -> dict:
        self._store.set(self._scope, self.key, body.get("value"))
        return self.serialize()
