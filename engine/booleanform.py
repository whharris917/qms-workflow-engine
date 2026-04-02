"""BooleanForm — binary yes/no toggle."""

from __future__ import annotations

from dataclasses import dataclass

from engine.affordances import Affordance
from engine.eigenform import Eigenform
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
class BooleanForm(Eigenform):
    """Binary yes/no toggle. Distinct from CheckboxForm (multi-select)."""
    true_label: str = "Yes"
    false_label: str = "No"

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
        return render_template("boolean.html", data=data, ef=self,
                               url=self.url, label=data["label"],
                               instruction=data.get("instruction") or "")

    def _handle(self, body: dict) -> dict:
        action = body.get("action")

        if action in ("set_true_label", "set_false_label") and self.editable and self.edit_mode:
            self._push_undo()
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
