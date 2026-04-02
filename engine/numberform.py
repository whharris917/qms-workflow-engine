"""NumberForm — numeric input with min/max bounds, step, and optional integer constraint."""

from __future__ import annotations

from dataclasses import dataclass

from engine.affordances import Affordance
from engine.eigenform import Eigenform
from engine.templates import render_template


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

    def _snapshot_edit_state(self) -> dict:
        state = super()._snapshot_edit_state()
        state["__config"] = self._store.get(self._scope, f"{self.key}.__config")
        return state

    def _restore_edit_state(self, state: dict):
        super()._restore_edit_state(state)
        self._store.set(self._scope, f"{self.key}.__config", state.get("__config"))

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
            cfg = dict(self._effective_config)
            field = {"set_min": "min_val", "set_max": "max_val", "set_step": "step"}[action]
            cfg[field] = val
            self._store.set(self._scope, f"{self.key}.__config", cfg)
            return self.serialize()

        if action == "toggle_integer" and self.editable and self.edit_mode:
            self._push_undo()
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
