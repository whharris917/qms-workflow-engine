from __future__ import annotations

from dataclasses import dataclass

from engine.affordances import Affordance, SetValueAffordance
from engine.eigenform import Eigenform
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
class TextForm(Eigenform):
    """Free-form string input. Single-line by default; set multiline=True for
    textarea behavior. Optional min_length/max_length for validation."""
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
                    label=f"Set {self.effective_label}",
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
                label=f"Set {self.effective_label}",
                method="POST",
                url=self.url,
                body={"value": "<value>"},
                instruction=f"Replace <value> with the desired {self.effective_label.lower()}.",
            )
        ]

    def _handle(self, body: dict) -> dict:
        val = body.get("value", "")
        if self.min_length is not None and len(val) < self.min_length:
            return self._error(f"Text is too short ({len(val)} chars). Minimum: {self.min_length}", body=body)
        if self.max_length is not None and len(val) > self.max_length:
            return self._error(f"Text is too long ({len(val)} chars). Maximum: {self.max_length}", body=body)
        self._store.set(self._scope, self.key, body.get("value"))
        return self.serialize()
