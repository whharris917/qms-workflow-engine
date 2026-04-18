"""BooleanForm — binary yes/no toggle."""

from __future__ import annotations

from dataclasses import dataclass

from engine.affordances import Affordance
from engine.component import Component
from engine.templates import render_template


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
class BooleanForm(Component):
    """Binary yes/no toggle. Distinct from CheckboxForm (multi-select)."""
    form = "boolean"

    true_label: str = "Yes"
    false_label: str = "No"

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "value": self.value,
            "true_label": self.true_label,
            "false_label": self.false_label,
        }

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        affs.append(Affordance(
            label="Set True Label", method="POST", url=self.url,
            body={"action": "set_true_label", "label": "<label>"},
            instruction=f"Label shown when value is true. Current: {self.true_label}",
        ))
        affs.append(Affordance(
            label="Set False Label", method="POST", url=self.url,
            body={"action": "set_false_label", "label": "<label>"},
            instruction=f"Label shown when value is false. Current: {self.false_label}",
        ))
        return affs

    def get_affordances(self) -> list[Affordance]:
        return [
            ToggleAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": f"<true | false>"},
                instruction=f"Set to true ({self.true_label}) or false ({self.false_label}).",
                current=self.value,
                true_label=self.true_label,
                false_label=self.false_label,
            )
        ]

    def render_from_data(self, data: dict) -> str:
        return render_template("boolean.html", data=data, ef=self,
                               url=self.url, label=data["label"],
                               instruction=data.get("instruction") or "")

    _actions = {
        None: "_do_set",
        "set_true_label": "_do_set_config_label",
        "set_false_label": "_do_set_config_label",
    }

    def _do_set(self, body: dict) -> dict:
        raw = body.get("value")
        if isinstance(raw, bool):
            val = raw
        elif isinstance(raw, str):
            val = raw.lower() in ("true", "yes", "1")
        else:
            val = bool(raw)
        self._store.set(self._scope, self.key, val)
        return self.serialize()

    def _do_set_config_label(self, body: dict) -> dict:
        if not (self.editable and self.edit_mode):
            return self.serialize()
        self._push_undo()
        new_label = body.get("label", "").strip()
        if not new_label:
            return self._error("Label cannot be empty.", action=body.get("action"))
        field = "true_label" if body.get("action") == "set_true_label" else "false_label"
        self._set_my_config(field, new_label)
        return self.serialize()
