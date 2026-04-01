"""ChoiceForm — single selection from a list of options."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance, STYLE_CONFIRM
from engine.eigenform import Eigenform


class SelectAffordance(Affordance):
    """An affordance that selects one option from a list."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None, options: list[str] | None = None,
                 current: str | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.options = options or []
        self.current = current

    def _render_hints(self) -> dict:
        return {"type": "radio", "options": self.options, "current": self.current}


@dataclass
class ChoiceForm(Eigenform):
    """Single selection from a fixed set of options."""
    options: list[str] = field(default_factory=list)

    def __post_init__(self):
        from engine.listform import ListForm
        self._options_form = ListForm(
            key="__options",
            label="Options",
            allow_constraints=False,
        )

    @property
    def children(self) -> list[Eigenform]:
        if self.edit_mode:
            return [self._options_form]
        return []

    def _bind_children(self, store, url_prefix):
        from engine.listform import ListForm
        self._options_form = self._options_form.bind(
            store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
        # Seed initial options if no ListForm data exists yet
        if not self._options_form.value:
            for opt in self.options:
                self._options_form.handle({"action": "add", "value": opt})

    @property
    def _effective_options(self) -> list[str]:
        """Read current options from the child ListForm."""
        return [item["value"] for item in self._options_form.items]

    @property
    def is_complete(self) -> bool:
        return self.value is not None and self.value in self._effective_options

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "value": self.value,
            "options": self._effective_options,
        }

    def get_affordances(self) -> list[Affordance]:
        opts = self._effective_options
        opts_str = " | ".join(opts)
        return [
            SelectAffordance(
                label=f"Set {self.effective_label}",
                method="POST",
                url=self.url,
                body={"value": f"<{opts_str}>"},
                instruction=f"Select one of: {opts_str}.",
                options=opts,
                current=self.value,
            )
        ]

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html

        if data.get("edit_mode"):
            return self._render_edit_mode(data)

        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        html += f'<p><strong>Selected:</strong> {escape(str(data["value"] or "None"))}</p>'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        return html

    def _render_edit_mode(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        url = self.url
        label = data["label"]
        instruction = data.get("instruction") or ""

        # Label
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

        # Instruction
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

        # Options — render the child ListForm
        html += self._options_form.render()

        # Value — same as normal mode
        html += f'<p><strong>Selected:</strong> {escape(str(data["value"] or "None"))}</p>'

        # Mark edit affordances as rendered (label/instruction handled by inline forms)
        edit_actions = {"set_label", "set_instruction"}
        for aff in data.get("affordances", []):
            if aff.get("_rendered"):
                continue
            if aff.get("body", {}).get("action") in edit_actions:
                aff["_rendered"] = True
            else:
                html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        # Normal value setting
        value = body.get("value")
        if value in self._effective_options:
            self._store.set(self._scope, self.key, value)
        return self.serialize()
