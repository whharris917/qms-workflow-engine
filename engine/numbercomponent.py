"""NumberComponent — numeric input with min/max bounds, step, slider mode, and unit label."""

from __future__ import annotations

from dataclasses import dataclass

from engine.affordances import Affordance
from engine.component import Component
from engine.templates import render_template


class NumberInputAffordance(Affordance):
    """An affordance for numeric input with validation hints."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 min_val: float | None = None, max_val: float | None = None,
                 step: float | None = None, slider: bool = False,
                 current: float | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.min_val = min_val
        self.max_val = max_val
        self.step = step
        self.slider = slider
        self.current = current

    def _render_hints(self) -> dict:
        if self.slider:
            return {"type": "range_input", "min": self.min_val, "max": self.max_val,
                    "step": self.step, "current": self.current}
        return {"type": "number_input", "min": self.min_val, "max": self.max_val, "step": self.step}


@dataclass
class NumberComponent(Component):
    """Numeric input with optional bounds and step. Set slider=True for
    a range slider UI. Optional unit label for display."""
    min_val: float | None = None
    max_val: float | None = None
    step: float | None = None
    slider: bool = False
    unit: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        state = self._base_state() | {
            "value": self.value,
            "min": self.min_val,
            "max": self.max_val,
            "step": self.step,
        }
        if self.slider:
            state["slider"] = True
        if self.unit:
            state["unit"] = self.unit
        return state

    def get_affordances(self) -> list[Affordance]:
        parts = []
        if self.min_val is not None:
            parts.append(f"min {self.min_val}")
        if self.max_val is not None:
            parts.append(f"max {self.max_val}")
        hint = f" ({', '.join(parts)})" if parts else ""
        if self.slider:
            body_hint = f"<{self.min_val if self.min_val is not None else 0}..{self.max_val if self.max_val is not None else 100}>"
            instruction = f"Set a value between {self.min_val} and {self.max_val} (step {self.step or 1})."
        else:
            body_hint = "<number>"
            instruction = f"Enter a number{hint}."
        return [
            NumberInputAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": body_hint},
                instruction=instruction,
                min_val=self.min_val,
                max_val=self.max_val,
                step=self.step,
                slider=self.slider,
                current=self.value,
            )
        ]

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        affs.append(Affordance(
            label="Set Min", method="POST", url=self.url,
            body={"action": "set_min", "value": "<number or null>"},
            instruction=f"Set minimum bound. Current: {self.min_val}",
        ))
        affs.append(Affordance(
            label="Set Max", method="POST", url=self.url,
            body={"action": "set_max", "value": "<number or null>"},
            instruction=f"Set maximum bound. Current: {self.max_val}",
        ))
        affs.append(Affordance(
            label="Set Step", method="POST", url=self.url,
            body={"action": "set_step", "value": "<number or null>"},
            instruction=f"Set step size. Current: {self.step}",
        ))
        affs.append(Affordance(
            label="Toggle Slider", method="POST", url=self.url,
            body={"action": "toggle_slider"},
            instruction=f"Toggle slider display mode. Currently: {self.slider}",
        ))
        affs.append(Affordance(
            label="Set Unit", method="POST", url=self.url,
            body={"action": "set_unit", "value": "<string or null>"},
            instruction=f"Set unit label (e.g. 'kg', '%'). Current: {self.unit}",
        ))
        return affs

    def render_from_data(self, data: dict) -> str:
        return render_template("number.html", data=data, ef=self,
                               url=self.url, label=data["label"],
                               instruction=data.get("instruction") or "")

    def _handle(self, body: dict) -> dict:
        action = body.get("action")

        # Edit-mode config actions
        if action in ("set_min", "set_max", "set_step") and self.editable and self.edit_mode:
            self._push_undo()
            raw = body.get("value")
            if raw is None or raw == "" or raw == "null":
                val = None
            else:
                try:
                    val = float(raw)
                except (TypeError, ValueError):
                    return self._error(f"Invalid number: {raw}", body=body)
            field = {"set_min": "min_val", "set_max": "max_val", "set_step": "step"}[action]
            self._set_my_config(field, val)
            return self.serialize()

        if action == "toggle_slider" and self.editable and self.edit_mode:
            self._push_undo()
            self._set_my_config("slider", not self.slider)
            return self.serialize()

        if action == "set_unit" and self.editable and self.edit_mode:
            self._push_undo()
            raw = body.get("value")
            val = None if raw is None or raw == "" or raw == "null" else str(raw)
            self._set_my_config("unit", val)
            return self.serialize()

        # Normal value setting — read directly from self
        raw = body.get("value")
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return self._error(f"Invalid number: {raw}", body=body)
        if self.min_val is not None and val < self.min_val:
            return self._error(f"Value {val} is below minimum {self.min_val}", body=body)
        if self.max_val is not None and val > self.max_val:
            return self._error(f"Value {val} is above maximum {self.max_val}", body=body)
        if self.step is not None:
            base = self.min_val if self.min_val is not None else 0
            remainder = abs((val - base) % self.step)
            if min(remainder, self.step - remainder) > 1e-9:
                return self._error(f"Value {val} is not a valid step (step {self.step} from {base})", body=body)
        self._store.set(self._scope, self.key, val)
        return self.serialize()
