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
        return {"multiline": self.multiline, "min_length": self.min_length,
                "max_length": self.max_length}

    @property
    def is_complete(self) -> bool:
        val = self.value
        if val is None or val == "":
            return False
        cfg = self._effective_config
        min_len = cfg.get("min_length")
        if min_len is not None and len(val) < min_len:
            return False
        return True

    def _serialize_state(self) -> dict:
        cfg = self._effective_config
        state = self._base_state() | {
            "value": self.value if self.value is not None else self.default,
        }
        if cfg.get("multiline"):
            state["multiline"] = True
        if cfg.get("min_length") is not None:
            state["min_length"] = cfg["min_length"]
        if cfg.get("max_length") is not None:
            state["max_length"] = cfg["max_length"]
        return state

    def _template_context(self, data: dict) -> dict:
        cfg = self._effective_config
        return dict(data=data, ef=self,
                    url=self.url, label=data["label"],
                    instruction=data.get("instruction") or "",
                    value=data.get("value"),
                    multiline=cfg.get("multiline", False),
                    edit_mode=data.get("edit_mode", False),
                    has_data=self.has_data,
                    undo_depth=self._undo_depth if self.edit_mode else 0)

    def render_from_data(self, data: dict) -> str:
        return render_template("text_human.html", **self._template_context(data))

    def get_affordances(self) -> list[Affordance]:
        cfg = self._effective_config
        is_multiline = cfg.get("multiline", False)
        min_len = cfg.get("min_length")
        max_len = cfg.get("max_length")
        if is_multiline or min_len is not None or max_len is not None:
            parts = []
            if min_len:
                parts.append(f"min {min_len} chars")
            if max_len:
                parts.append(f"max {max_len} chars")
            hint = f" ({', '.join(parts)})" if parts else ""
            multi = "multi-line text" if is_multiline else "text"
            return [
                TextAffordance(
                    label=f"Set {self.effective_label}",
                    method="POST",
                    url=self.url,
                    body={"value": "<text>"},
                    instruction=f"Enter {multi}{hint}.",
                    multiline=is_multiline,
                    max_length=max_len,
                    min_length=min_len,
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

    def _get_edit_affordances(self) -> list[Affordance]:
        cfg = self._effective_config
        affs = super()._get_edit_affordances()
        affs.append(Affordance(
            label="Toggle Multiline", method="POST", url=self.url,
            body={"action": "toggle_multiline"},
            instruction=f"Toggle multiline (textarea) mode. Currently: {cfg.get('multiline', False)}",
        ))
        affs.append(Affordance(
            label="Set Min Length", method="POST", url=self.url,
            body={"action": "set_min_length", "value": "<integer or null>"},
            instruction=f"Set minimum character length. Current: {cfg.get('min_length')}",
        ))
        affs.append(Affordance(
            label="Set Max Length", method="POST", url=self.url,
            body={"action": "set_max_length", "value": "<integer or null>"},
            instruction=f"Set maximum character length. Current: {cfg.get('max_length')}",
        ))
        return affs

    def _handle(self, body: dict) -> dict:
        action = body.get("action")

        # Edit-mode config actions
        if action == "toggle_multiline" and self.editable and self.edit_mode:
            self._push_undo()
            cfg = dict(self._effective_config)
            cfg["multiline"] = not cfg.get("multiline", False)
            self._store.set(self._scope, f"{self.key}.__config", cfg)
            return self.serialize()

        if action in ("set_min_length", "set_max_length") and self.editable and self.edit_mode:
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
            cfg = dict(self._effective_config)
            field = "min_length" if action == "set_min_length" else "max_length"
            cfg[field] = val
            self._store.set(self._scope, f"{self.key}.__config", cfg)
            return self.serialize()

        # Normal value setting — use effective config for validation
        cfg = self._effective_config
        min_len = cfg.get("min_length")
        max_len = cfg.get("max_length")
        val = body.get("value", "")
        if min_len is not None and len(val) < min_len:
            return self._error(f"Text is too short ({len(val)} chars). Minimum: {min_len}", body=body)
        if max_len is not None and len(val) > max_len:
            return self._error(f"Text is too long ({len(val)} chars). Maximum: {max_len}", body=body)
        self._store.set(self._scope, self.key, body.get("value"))
        return self.serialize()
