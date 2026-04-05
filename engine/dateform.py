"""DateForm — date (or datetime) input with ISO 8601 strings."""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.affordances import Affordance
from engine.eigenform import Eigenform
from engine.templates import render_template

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$")


class DateInputAffordance(Affordance):
    """An affordance for date/datetime input."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 include_time: bool = False,
                 min_date: str | None = None, max_date: str | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.include_time = include_time
        self.min_date = min_date
        self.max_date = max_date

    def _render_hints(self) -> dict:
        return {
            "type": "date_input",
            "include_time": self.include_time,
            "min": self.min_date,
            "max": self.max_date,
        }


@dataclass
class DateForm(Eigenform):
    """Date or datetime input, stored as ISO 8601 string."""
    include_time: bool = False
    min_date: str | None = None
    max_date: str | None = None

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
        return {"include_time": self.include_time, "min_date": self.min_date,
                "max_date": self.max_date}

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        cfg = self._effective_config
        inc_time = cfg.get("include_time", False)
        fmt = "YYYY-MM-DDTHH:MM" if inc_time else "YYYY-MM-DD"
        return self._base_state() | {
            "value": self.value,
            "format": fmt,
            "include_time": inc_time,
            "min": cfg.get("min_date"),
            "max": cfg.get("max_date"),
        }

    def get_affordances(self) -> list[Affordance]:
        cfg = self._effective_config
        inc_time = cfg.get("include_time", False)
        fmt = "YYYY-MM-DDTHH:MM" if inc_time else "YYYY-MM-DD"
        return [
            DateInputAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": f"<{fmt}>"},
                instruction=f"Enter a date in {fmt} format.",
                include_time=inc_time,
                min_date=cfg.get("min_date"),
                max_date=cfg.get("max_date"),
            )
        ]

    def _get_edit_affordances(self) -> list[Affordance]:
        cfg = self._effective_config
        affs = super()._get_edit_affordances()
        affs.append(Affordance(
            label="Toggle Include Time", method="POST", url=self.url,
            body={"action": "toggle_include_time"},
            instruction=f"Toggle datetime mode (YYYY-MM-DDTHH:MM). Currently: {cfg.get('include_time', False)}",
        ))
        affs.append(Affordance(
            label="Set Min Date", method="POST", url=self.url,
            body={"action": "set_min_date", "value": "<YYYY-MM-DD or null>"},
            instruction=f"Set earliest allowed date. Current: {cfg.get('min_date')}",
        ))
        affs.append(Affordance(
            label="Set Max Date", method="POST", url=self.url,
            body={"action": "set_max_date", "value": "<YYYY-MM-DD or null>"},
            instruction=f"Set latest allowed date. Current: {cfg.get('max_date')}",
        ))
        return affs

    def render_from_data(self, data: dict) -> str:
        return render_template("date.html", data=data, ef=self,
                               url=self.url, label=data["label"],
                               instruction=data.get("instruction") or "")

    def _handle(self, body: dict) -> dict:
        action = body.get("action")

        # Edit-mode config actions
        if action == "toggle_include_time" and self.editable and self.edit_mode:
            self._push_undo()
            cfg = dict(self._effective_config)
            cfg["include_time"] = not cfg.get("include_time", False)
            self._store.set(self._scope, f"{self.key}.__config", cfg)
            return self.serialize()

        if action in ("set_min_date", "set_max_date") and self.editable and self.edit_mode:
            self._push_undo()
            raw = body.get("value")
            if raw is None or raw == "" or raw == "null":
                val = None
            else:
                if not DATE_RE.match(raw):
                    return self._error(f"Invalid date format. Expected YYYY-MM-DD, got: {raw}", body=body)
                val = raw
            cfg = dict(self._effective_config)
            field = "min_date" if action == "set_min_date" else "max_date"
            cfg[field] = val
            self._store.set(self._scope, f"{self.key}.__config", cfg)
            return self.serialize()

        # Normal value setting — use effective config for validation
        cfg = self._effective_config
        inc_time = cfg.get("include_time", False)
        min_d = cfg.get("min_date")
        max_d = cfg.get("max_date")
        raw = body.get("value", "")
        pattern = DATETIME_RE if inc_time else DATE_RE
        if not pattern.match(raw):
            fmt = "YYYY-MM-DDTHH:MM" if inc_time else "YYYY-MM-DD"
            return self._error(f"Invalid date format. Expected {fmt}, got: {raw}", body=body)
        if min_d and raw < min_d:
            return self._error(f"Date {raw} is before minimum {min_d}", body=body)
        if max_d and raw > max_d:
            return self._error(f"Date {raw} is after maximum {max_d}", body=body)
        self._store.set(self._scope, self.key, raw)
        return self.serialize()
