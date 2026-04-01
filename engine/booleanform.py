"""BooleanForm — binary yes/no toggle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from typing import Any

from engine.affordances import Affordance, STYLE_CONFIRM
from engine.eigenform import Eigenform


class ToggleAffordance(Affordance):
    """An affordance showing a yes/no toggle with active state."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 current: bool | None = None,
                 true_label: str = "Yes", false_label: str = "No"):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.current = current
        self.true_label = true_label
        self.false_label = false_label

    def _render_hints(self) -> dict:
        return {
            "type": "toggle",
            "current": self.current,
            "true_label": self.true_label,
            "false_label": self.false_label,
        }


@dataclass
class BooleanForm(Eigenform):
    """Binary yes/no toggle. Distinct from CheckboxForm (multi-select)."""
    true_label: str = "Yes"
    false_label: str = "No"

    @property
    def _effective_config(self) -> dict:
        """Config from store override if set, else Python defaults."""
        if self._store is not None:
            override = self._store.get(self._scope, f"{self.key}.__config")
            if override is not None:
                return override
        return {"true_label": self.true_label, "false_label": self.false_label}

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        cfg = self._effective_config
        return self._base_state() | {
            "value": self.value,
            "true_label": cfg["true_label"],
            "false_label": cfg["false_label"],
        }

    def _get_edit_affordances(self) -> list[Affordance]:
        cfg = self._effective_config
        affs = super()._get_edit_affordances()
        affs.append(Affordance(
            label="Set True Label", method="POST", url=self.url,
            body={"action": "set_true_label", "label": "<label>"},
            instruction=f"Label shown when value is true. Current: {cfg['true_label']}",
        ))
        affs.append(Affordance(
            label="Set False Label", method="POST", url=self.url,
            body={"action": "set_false_label", "label": "<label>"},
            instruction=f"Label shown when value is false. Current: {cfg['false_label']}",
        ))
        return affs

    def get_affordances(self) -> list[Affordance]:
        cfg = self._effective_config
        return [
            ToggleAffordance(
                label=f"Set {self.effective_label}",
                method="POST",
                url=self.url,
                body={"value": f"<true | false>"},
                instruction=f"Set to true ({cfg['true_label']}) or false ({cfg['false_label']}).",
                current=self.value,
                true_label=cfg["true_label"],
                false_label=cfg["false_label"],
            )
        ]

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html

        if data.get("edit_mode"):
            return self._render_edit_mode(data)

        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        val = data["value"]
        if val is None:
            display = "Not set"
        elif val:
            display = data["true_label"]
        else:
            display = data["false_label"]
        html += f'<p><strong>Value:</strong> {escape(display)}</p>'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        return html

    def _render_edit_mode(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        url = self.url
        label = data["label"]
        instruction = data.get("instruction") or ""

        def inline_input(action, field, current_val, *, font_size="inherit",
                         font_weight="normal", placeholder="", width="100%"):
            body = json.dumps({"action": action, field: str(current_val)})
            tooltip = f'POST {url} {escape(body)}'
            return (
                f'<form style="display: flex; align-items: center; gap: 4px;"'
                f' onsubmit="fetch(\'{url}\','
                f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f'body:JSON.stringify({{action:\'{action}\',{field}:this.elements.v.value}})'
                f'}}).then(()=>location.reload()); return false">'
                f'<input name="v" type="text" value="{escape(str(current_val))}"'
                f' placeholder="{escape(placeholder)}"'
                f' style="font: inherit; font-size: {font_size}; font-weight: {font_weight};'
                f' border: 1px solid #ddd; padding: 1px 3px; margin: 0; width: {width};"'
                f' title="{tooltip}" />'
                f' <button type="submit" style="{STYLE_CONFIRM}"'
                f' title="{tooltip}">&#10003;</button>'
                f'</form>'
            )

        # Label
        html = f'<div style="margin: 0.83em 0;">'
        html += inline_input("set_label", "label", label,
                             font_size="1.17em", font_weight="bold")
        html += '</div>'

        # Instruction
        html += f'<div style="margin: 1em 0;">'
        html += inline_input("set_instruction", "instruction", instruction,
                             placeholder="Instruction text")
        html += '</div>'

        # True/False labels — inline row
        html += '<div style="display: flex; gap: 12px; align-items: center; margin: 4px 0; font-size: 0.9em; color: #666;">'
        for lbl, action, field_val in [
            ("True label", "set_true_label", data["true_label"]),
            ("False label", "set_false_label", data["false_label"]),
        ]:
            body_json = json.dumps({"action": action, "label": field_val})
            tooltip = f'POST {url} {escape(body_json)}'
            html += (
                f'<form style="display: flex; align-items: center; gap: 2px; margin: 0;"'
                f' onsubmit="fetch(\'{url}\','
                f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f'body:JSON.stringify({{action:\'{action}\',label:this.elements.v.value}})'
                f'}}).then(()=>location.reload()); return false">'
                f'<span style="font-weight: 600;">{lbl}:</span>'
                f'<input name="v" type="text" value="{escape(field_val)}"'
                f' style="font: inherit; border: 1px solid #ddd; padding: 1px 3px;'
                f' margin: 0; width: 80px;"'
                f' title="{tooltip}" />'
                f'<button type="submit" style="{STYLE_CONFIRM}"'
                f' title="{tooltip}">&#10003;</button>'
                f'</form>'
            )
        html += '</div>'

        # Value — same as normal mode
        val = data["value"]
        if val is None:
            display = "Not set"
        elif val:
            display = data["true_label"]
        else:
            display = data["false_label"]
        html += f'<p><strong>Value:</strong> {escape(display)}</p>'

        # Mark edit affordances as rendered
        edit_actions = {"set_label", "set_instruction", "set_true_label", "set_false_label"}
        for aff in data.get("affordances", []):
            if aff.get("_rendered"):
                continue
            if aff.get("body", {}).get("action") in edit_actions:
                aff["_rendered"] = True
            else:
                html += render_affordance_html(aff)
        return html

    def _handle(self, body: dict) -> dict:
        action = body.get("action")

        # Edit-mode config actions
        if action in ("set_true_label", "set_false_label") and self.editable and self.edit_mode:
            new_label = body.get("label", "").strip()
            if not new_label:
                return self._error("Label cannot be empty.", action=action)
            cfg = dict(self._effective_config)
            field = "true_label" if action == "set_true_label" else "false_label"
            cfg[field] = new_label
            self._store.set(self._scope, f"{self.key}.__config", cfg)
            return self.serialize()

        # Normal value setting
        raw = body.get("value")
        if isinstance(raw, bool):
            val = raw
        elif isinstance(raw, str):
            val = raw.lower() in ("true", "yes", "1")
        else:
            val = bool(raw)
        self._store.set(self._scope, self.key, val)
        return self.serialize()
