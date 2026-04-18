"""DateForm — date (or datetime) input with ISO 8601 strings."""

from __future__ import annotations

import re
from dataclasses import dataclass

from engine.affordances import Affordance
from engine.component import Component
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
class DateForm(Component):
    """Date or datetime input, stored as ISO 8601 string."""
    form = "date"

    include_time: bool = False
    min_date: str | None = None
    max_date: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        fmt = "YYYY-MM-DDTHH:MM" if self.include_time else "YYYY-MM-DD"
        return self._base_state() | {
            "value": self.value,
            "format": fmt,
            "include_time": self.include_time,
            "min": self.min_date,
            "max": self.max_date,
        }

    def get_affordances(self) -> list[Affordance]:
        fmt = "YYYY-MM-DDTHH:MM" if self.include_time else "YYYY-MM-DD"
        return [
            DateInputAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": f"<{fmt}>"},
                instruction=f"Enter a date in {fmt} format.",
                include_time=self.include_time,
                min_date=self.min_date,
                max_date=self.max_date,
            )
        ]

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        affs.append(Affordance(
            label="Toggle Include Time", method="POST", url=self.url,
            body={"action": "toggle_include_time"},
            instruction=f"Toggle datetime mode (YYYY-MM-DDTHH:MM). Currently: {self.include_time}",
        ))
        affs.append(Affordance(
            label="Set Min Date", method="POST", url=self.url,
            body={"action": "set_min_date", "value": "<YYYY-MM-DD or null>"},
            instruction=f"Set earliest allowed date. Current: {self.min_date}",
        ))
        affs.append(Affordance(
            label="Set Max Date", method="POST", url=self.url,
            body={"action": "set_max_date", "value": "<YYYY-MM-DD or null>"},
            instruction=f"Set latest allowed date. Current: {self.max_date}",
        ))
        return affs

    def render_from_data(self, data: dict) -> str:
        return render_template("date.html", data=data, ef=self,
                               url=self.url, label=data["label"],
                               instruction=data.get("instruction") or "")

    _actions = {
        None: "_do_set",
        "toggle_include_time": "_do_toggle_include_time",
        "set_min_date": "_do_set_date_bound",
        "set_max_date": "_do_set_date_bound",
    }

    def _do_set(self, body: dict) -> dict:
        raw = body.get("value", "")
        pattern = DATETIME_RE if self.include_time else DATE_RE
        if not pattern.match(raw):
            fmt = "YYYY-MM-DDTHH:MM" if self.include_time else "YYYY-MM-DD"
            return self._error(f"Invalid date format. Expected {fmt}, got: {raw}", body=body)
        if self.min_date and raw < self.min_date:
            return self._error(f"Date {raw} is before minimum {self.min_date}", body=body)
        if self.max_date and raw > self.max_date:
            return self._error(f"Date {raw} is after maximum {self.max_date}", body=body)
        self._store.set(self._scope, self.key, raw)
        return self.serialize()

    def _do_toggle_include_time(self, body: dict) -> dict:
        if not (self.editable and self.edit_mode):
            return self.serialize()
        self._push_undo()
        self._set_my_config("include_time", not self.include_time)
        return self.serialize()

    def _do_set_date_bound(self, body: dict) -> dict:
        if not (self.editable and self.edit_mode):
            return self.serialize()
        self._push_undo()
        raw = body.get("value")
        if raw is None or raw == "" or raw == "null":
            val = None
        else:
            if not DATE_RE.match(raw):
                return self._error(f"Invalid date format. Expected YYYY-MM-DD, got: {raw}", body=body)
            val = raw
        action = body.get("action")
        field = "min_date" if action == "set_min_date" else "max_date"
        self._set_my_config(field, val)
        return self.serialize()
