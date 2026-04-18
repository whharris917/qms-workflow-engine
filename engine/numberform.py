"""NumberForm — numeric input with min/max bounds, step, slider mode, and unit label."""

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
class NumberForm(Component):
    """Numeric input with optional bounds and step. Set slider=True for
    a range slider UI. Optional unit label for display.

    `min_val`, `max_val`, and `step` may hold a `SiblingBind` — the bound
    field resolves from the referenced sibling's current value at every
    serialize and on every action.
    """
    form = "number"

    min_val: float | None = None
    max_val: float | None = None
    step: float | None = None
    slider: bool = False
    unit: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        resolved_min = self._resolve_field("min_val")
        resolved_max = self._resolve_field("max_val")
        resolved_step = self._resolve_field("step")
        state = self._base_state() | {
            "value": self.value,
            "min": resolved_min,
            "max": resolved_max,
            "step": resolved_step,
        }
        if self.slider:
            state["slider"] = True
        if self.unit:
            state["unit"] = self.unit
        # Stale: a stored value that falls outside the currently resolved
        # bounds is flagged rather than silently accepted.
        val = self.value
        if val is not None:
            if (resolved_min is not None and val < resolved_min) or \
               (resolved_max is not None and val > resolved_max):
                state["stale"] = True
        return state

    def get_affordances(self) -> list[Affordance]:
        resolved_min = self._resolve_field("min_val")
        resolved_max = self._resolve_field("max_val")
        resolved_step = self._resolve_field("step")
        parts = []
        if resolved_min is not None:
            parts.append(f"min {resolved_min}")
        if resolved_max is not None:
            parts.append(f"max {resolved_max}")
        hint = f" ({', '.join(parts)})" if parts else ""
        if self.slider:
            body_hint = f"<{resolved_min if resolved_min is not None else 0}..{resolved_max if resolved_max is not None else 100}>"
            instruction = f"Set a value between {resolved_min} and {resolved_max} (step {resolved_step or 1})."
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
                min_val=resolved_min,
                max_val=resolved_max,
                step=resolved_step,
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

    _actions = {
        None: "_do_set",
        "set_min": "_do_set_bound",
        "set_max": "_do_set_bound",
        "set_step": "_do_set_bound",
        "toggle_slider": "_do_toggle_slider",
        "set_unit": "_do_set_unit",
    }

    def _do_set(self, body: dict) -> dict:
        raw = body.get("value")
        try:
            val = float(raw)
        except (TypeError, ValueError):
            return self._error(f"Invalid number: {raw}", body=body)
        resolved_min = self._resolve_field("min_val")
        resolved_max = self._resolve_field("max_val")
        resolved_step = self._resolve_field("step")
        if resolved_min is not None and val < resolved_min:
            return self._error(f"Value {val} is below minimum {resolved_min}", body=body)
        if resolved_max is not None and val > resolved_max:
            return self._error(f"Value {val} is above maximum {resolved_max}", body=body)
        if resolved_step is not None:
            base = resolved_min if resolved_min is not None else 0
            remainder = abs((val - base) % resolved_step)
            if min(remainder, resolved_step - remainder) > 1e-9:
                return self._error(f"Value {val} is not a valid step (step {resolved_step} from {base})", body=body)
        self._store.set(self._scope, self.key, val)
        return self.serialize()

    def _do_set_bound(self, body: dict) -> dict:
        if not (self.editable and self.edit_mode):
            return self.serialize()
        self._push_undo()
        raw = body.get("value")
        if raw is None or raw == "" or raw == "null":
            val = None
        else:
            try:
                val = float(raw)
            except (TypeError, ValueError):
                return self._error(f"Invalid number: {raw}", body=body)
        action = body.get("action")
        field = {"set_min": "min_val", "set_max": "max_val", "set_step": "step"}[action]
        self._set_my_config(field, val)
        return self.serialize()

    def _do_toggle_slider(self, body: dict) -> dict:
        if not (self.editable and self.edit_mode):
            return self.serialize()
        self._push_undo()
        self._set_my_config("slider", not self.slider)
        return self.serialize()

    def _do_set_unit(self, body: dict) -> dict:
        if not (self.editable and self.edit_mode):
            return self.serialize()
        self._push_undo()
        raw = body.get("value")
        val = None if raw is None or raw == "" or raw == "null" else str(raw)
        self._set_my_config("unit", val)
        return self.serialize()
