from __future__ import annotations

from dataclasses import dataclass

from engine.affordances import Affordance, SetValueAffordance
from engine.component import Component
from engine.templates import render_template


class TextAffordance(Affordance):
    """An affordance with render hints for multiline/length constraints."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 multiline: bool = False,
                 max_length: int | None = None, min_length: int | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.multiline = multiline
        self.max_length = max_length
        self.min_length = min_length

    def _render_hints(self) -> dict:
        hints: dict = {}
        if self.multiline:
            hints["type"] = "textarea"
        if self.max_length is not None:
            hints["max_length"] = self.max_length
        if self.min_length is not None:
            hints["min_length"] = self.min_length
        return hints


@dataclass
class TextForm(Component):
    """Free-form string input. Single-line by default; set multiline=True for
    textarea behavior. Optional min_length/max_length for validation."""
    form = "text"

    default: str | None = None
    multiline: bool = False
    min_length: int | None = None
    max_length: int | None = None

    @property
    def is_complete(self) -> bool:
        val = self.value
        if val is None or val == "":
            return False
        if self.min_length is not None and len(val) < self.min_length:
            return False
        return True

    def _serialize_state(self) -> dict:
        state = self._base_state() | {
            "value": self.value if self.value is not None else self.default,
        }
        if self.multiline:
            state["multiline"] = True
        if self.min_length is not None:
            state["min_length"] = self.min_length
        if self.max_length is not None:
            state["max_length"] = self.max_length
        return state

    def _template_context(self, data: dict) -> dict:
        return dict(data=data, ef=self,
                    url=self.url, label=data["label"],
                    instruction=data.get("instruction") or "",
                    value=data.get("value"),
                    multiline=self.multiline,
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data,
                    undo_depth=self._undo_depth if self.edit_mode else 0)

    def render_from_data(self, data: dict) -> str:
        return render_template("text_human.html", **self._template_context(data))

    def get_affordances(self) -> list[Affordance]:
        if self.multiline or self.min_length is not None or self.max_length is not None:
            parts = []
            if self.min_length:
                parts.append(f"min {self.min_length} chars")
            if self.max_length:
                parts.append(f"max {self.max_length} chars")
            hint = f" ({', '.join(parts)})" if parts else ""
            multi = "multi-line text" if self.multiline else "text"
            return [
                TextAffordance(
                    label=f"Set {self.label}",
                    method="POST",
                    url=self.url,
                    body={"value": "<text>"},
                    instruction=f"Enter {multi}{hint}.",
                    multiline=self.multiline,
                    max_length=self.max_length,
                    min_length=self.min_length,
                )
            ]
        return [
            SetValueAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": "<value>"},
                instruction=f"Replace <value> with the desired {self.label.lower()}.",
            )
        ]

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        affs.append(Affordance(
            label="Toggle Multiline", method="POST", url=self.url,
            body={"action": "toggle_multiline"},
            instruction=f"Toggle multiline (textarea) mode. Currently: {self.multiline}",
        ))
        affs.append(Affordance(
            label="Set Min Length", method="POST", url=self.url,
            body={"action": "set_min_length", "value": "<integer or null>"},
            instruction=f"Set minimum character length. Current: {self.min_length}",
        ))
        affs.append(Affordance(
            label="Set Max Length", method="POST", url=self.url,
            body={"action": "set_max_length", "value": "<integer or null>"},
            instruction=f"Set maximum character length. Current: {self.max_length}",
        ))
        return affs

    _actions = {
        None: "_do_set",
        "toggle_multiline": "_do_toggle_multiline",
        "set_min_length": "_do_set_length",
        "set_max_length": "_do_set_length",
    }

    def _do_set(self, body: dict) -> dict:
        val = body.get("value", "")
        if self.min_length is not None and len(val) < self.min_length:
            return self._error(f"Text is too short ({len(val)} chars). Minimum: {self.min_length}", body=body)
        if self.max_length is not None and len(val) > self.max_length:
            return self._error(f"Text is too long ({len(val)} chars). Maximum: {self.max_length}", body=body)
        self._store.set(self._scope, self.key, body.get("value"))
        return self.serialize()

    def _do_toggle_multiline(self, body: dict) -> dict:
        if not (self.editable and self.edit_mode):
            return self.serialize()
        self._push_undo()
        self._set_my_config("multiline", not self.multiline)
        return self.serialize()

    def _do_set_length(self, body: dict) -> dict:
        if not (self.editable and self.edit_mode):
            return self.serialize()
        self._push_undo()
        raw = body.get("value")
        if raw is None or raw == "" or raw == "null":
            val = None
        else:
            try:
                val = int(raw)
                if val < 0:
                    return self._error("Length must be non-negative", body=body)
            except (TypeError, ValueError):
                return self._error(f"Invalid integer: {raw}", body=body)
        field = "min_length" if body.get("action") == "set_min_length" else "max_length"
        self._set_my_config(field, val)
        return self.serialize()
