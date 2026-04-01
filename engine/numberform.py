"""NumberForm — numeric input with min/max bounds, step, and optional integer constraint."""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape
from typing import Any

from engine.affordances import Affordance, STYLE_CONFIRM
from engine.eigenform import Eigenform


class NumberInputAffordance(Affordance):
    """An affordance for numeric input with validation hints."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 min_val: float | None = None, max_val: float | None = None,
                 step: float | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.min_val = min_val
        self.max_val = max_val
        self.step = step

    def _render_hints(self) -> dict:
        return {"type": "number_input", "min": self.min_val, "max": self.max_val, "step": self.step}


@dataclass
class NumberForm(Eigenform):
    """Numeric input with optional bounds and step."""
    min_val: float | None = None
    max_val: float | None = None
    step: float | None = None
    integer: bool = False

    @property
    def _effective_config(self) -> dict:
        """Config from store override if set, else Python defaults."""
        if self._store is not None:
            override = self._store.get(self._scope, f"{self.key}.__config")
            if override is not None:
                return override
        return {"min_val": self.min_val, "max_val": self.max_val,
                "step": self.step, "integer": self.integer}

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        cfg = self._effective_config
        return self._base_state() | {
            "value": self.value,
            "min": cfg.get("min_val"),
            "max": cfg.get("max_val"),
            "step": cfg.get("step"),
            "integer": cfg.get("integer", False),
        }

    def get_affordances(self) -> list[Affordance]:
        cfg = self._effective_config
        min_v, max_v = cfg.get("min_val"), cfg.get("max_val")
        step_v, int_v = cfg.get("step"), cfg.get("integer", False)
        parts = []
        if int_v:
            parts.append("integer only")
        if min_v is not None:
            parts.append(f"min {min_v}")
        if max_v is not None:
            parts.append(f"max {max_v}")
        hint = f" ({', '.join(parts)})" if parts else ""
        return [
            NumberInputAffordance(
                label=f"Set {self.effective_label}",
                method="POST",
                url=self.url,
                body={"value": "<number>"},
                instruction=f"Enter a number{hint}.",
                min_val=min_v,
                max_val=max_v,
                step=step_v,
            )
        ]

    def _get_edit_affordances(self) -> list[Affordance]:
        cfg = self._effective_config
        affs = super()._get_edit_affordances()
        affs.append(Affordance(
            label="Set Min", method="POST", url=self.url,
            body={"action": "set_min", "value": "<number or null>"},
            instruction=f"Set minimum bound. Current: {cfg.get('min_val')}",
        ))
        affs.append(Affordance(
            label="Set Max", method="POST", url=self.url,
            body={"action": "set_max", "value": "<number or null>"},
            instruction=f"Set maximum bound. Current: {cfg.get('max_val')}",
        ))
        affs.append(Affordance(
            label="Set Step", method="POST", url=self.url,
            body={"action": "set_step", "value": "<number or null>"},
            instruction=f"Set step size. Current: {cfg.get('step')}",
        ))
        affs.append(Affordance(
            label="Toggle Integer", method="POST", url=self.url,
            body={"action": "toggle_integer"},
            instruction=f"Toggle integer-only constraint. Currently: {cfg.get('integer', False)}",
        ))
        return affs

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html

        if data.get("edit_mode"):
            return self._render_edit_mode(data)

        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        # Constraints summary
        constraints = []
        if data.get("min") is not None:
            constraints.append(f'min: {data["min"]}')
        if data.get("max") is not None:
            constraints.append(f'max: {data["max"]}')
        if data.get("step") is not None:
            constraints.append(f'step: {data["step"]}')
        if data.get("integer"):
            constraints.append("integer")
        if constraints:
            html += (
                f'<p style="color: #666; font-size: 0.9em; margin: 2px 0;">'
                f'{escape(", ".join(constraints))}</p>'
            )

        val = data["value"]
        html += f'<p><strong>Value:</strong> {escape(str(val if val is not None else "None"))}</p>'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        return html

    def _render_edit_mode(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        url = self.url
        label = data["label"]
        instruction = data.get("instruction") or ""

        def inline_form(name, action_key, action_field, current_val, *,
                        font_size="inherit", font_weight="normal",
                        placeholder="", input_type="text", width="100%"):
            body = json.dumps({"action": action_key, action_field: str(current_val)})
            tooltip = f'POST {url} {escape(body)}'
            return (
                f'<form style="display: flex; align-items: center; gap: 4px;"'
                f' onsubmit="fetch(\'{url}\','
                f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f'body:JSON.stringify({{action:\'{action_key}\',{action_field}:this.elements.v.value}})'
                f'}}).then(()=>location.reload()); return false">'
                f'<input name="v" type="{input_type}" value="{escape(str(current_val))}"'
                f' placeholder="{escape(placeholder)}"'
                f' style="font: inherit; font-size: {font_size}; font-weight: {font_weight};'
                f' border: 1px solid #ddd; padding: 1px 3px; margin: 0; width: {width};"'
                f' title="{tooltip}" />'
                f' <button type="submit" style="{STYLE_CONFIRM}"'
                f' title="{tooltip}">&#10003;</button>'
                f'</form>'
            )

        # Label — matches <h3> position
        html = f'<div style="margin: 0.83em 0;">'
        html += inline_form("label", "set_label", "label", label,
                            font_size="1.17em", font_weight="bold")
        html += '</div>'

        # Instruction — matches <p> position
        html += f'<div style="margin: 1em 0;">'
        html += inline_form("instruction", "set_instruction", "instruction", instruction,
                            placeholder="Instruction text")
        html += '</div>'

        # Constraints — editable row per config field
        html += '<div style="margin: 2px 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 0.9em; color: #666;">'
        for field_label, action, field_name, val in [
            ("min", "set_min", "value", data.get("min")),
            ("max", "set_max", "value", data.get("max")),
            ("step", "set_step", "value", data.get("step")),
        ]:
            display_val = "" if val is None else str(val)
            body_json = json.dumps({"action": action, field_name: display_val})
            tooltip = f'POST {url} {escape(body_json)}'
            html += (
                f'<form style="display: flex; align-items: center; gap: 2px; margin: 0;"'
                f' onsubmit="var v=this.elements.v.value;'
                f'fetch(\'{url}\',{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f'body:JSON.stringify({{action:\'{action}\',{field_name}:v||null}})'
                f'}}).then(()=>location.reload()); return false">'
                f'<span style="font-weight: 600;">{field_label}:</span>'
                f'<input name="v" type="text" value="{escape(display_val)}"'
                f' placeholder="none"'
                f' style="font: inherit; border: 1px solid #ddd; padding: 1px 3px;'
                f' margin: 0; width: 60px; text-align: center;"'
                f' title="{tooltip}" />'
                f'<button type="submit" style="{STYLE_CONFIRM}"'
                f' title="{tooltip}">&#10003;</button>'
                f'</form>'
            )

        # Integer toggle — checkbox-style button
        int_val = data.get("integer", False)
        int_body = json.dumps({"action": "toggle_integer"})
        int_tooltip = f'POST {url} {escape(int_body)}'
        int_bg = "#efffef" if int_val else "#f8f8f8"
        int_border = "#4a4" if int_val else "#ccc"
        html += (
            f'<button onclick="fetch(\'{url}\','
            f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
            f'body:JSON.stringify({int_body.replace(chr(34), "&quot;")})}}).then(()=>location.reload())"'
            f' style="cursor: pointer; font: inherit; font-size: 0.9em; border: 1px solid {int_border};'
            f' background: {int_bg}; padding: 1px 8px; border-radius: 3px;"'
            f' title="{int_tooltip}">integer: {"on" if int_val else "off"}</button>'
        )
        html += '</div>'

        # Value — same as normal mode
        val = data["value"]
        html += f'<p><strong>Value:</strong> {escape(str(val if val is not None else "None"))}</p>'

        # Mark edit affordances as rendered
        edit_actions = {"set_label", "set_instruction", "set_min", "set_max", "set_step", "toggle_integer"}
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
        if action in ("set_min", "set_max", "set_step") and self.editable and self.edit_mode:
            raw = body.get("value")
            if raw is None or raw == "" or raw == "null":
                val = None
            else:
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    return self._error(f"Invalid number: {raw}", body=body)
            cfg = dict(self._effective_config)
            field = {"set_min": "min_val", "set_max": "max_val", "set_step": "step"}[action]
            cfg[field] = val
            self._store.set(self._scope, f"{self.key}.__config", cfg)
            return self.serialize()

        if action == "toggle_integer" and self.editable and self.edit_mode:
            cfg = dict(self._effective_config)
            cfg["integer"] = not cfg.get("integer", False)
            self._store.set(self._scope, f"{self.key}.__config", cfg)
            return self.serialize()

        # Normal value setting — use effective config for validation
        cfg = self._effective_config
        min_v, max_v = cfg.get("min_val"), cfg.get("max_val")
        step_v, int_v = cfg.get("step"), cfg.get("integer", False)
        raw = body.get("value")
        try:
            val = int(raw) if int_v else float(raw)
        except (TypeError, ValueError):
            return self._error(f"Invalid number: {raw}", body=body)
        if min_v is not None and val < min_v:
            return self._error(f"Value {val} is below minimum {min_v}", body=body)
        if max_v is not None and val > max_v:
            return self._error(f"Value {val} is above maximum {max_v}", body=body)
        if step_v is not None:
            base = min_v if min_v is not None else 0
            remainder = abs((val - base) % step_v)
            if min(remainder, step_v - remainder) > 1e-9:
                return self._error(f"Value {val} is not a valid step (step {step_v} from {base})", body=body)
        self._store.set(self._scope, self.key, val)
        return self.serialize()
