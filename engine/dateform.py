"""DateForm — date (or datetime) input with ISO 8601 strings."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape

from engine.affordances import Affordance
from engine.bases import ScalarForm

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
class DateForm(ScalarForm):
    """Date or datetime input, stored as ISO 8601 string."""
    include_time: bool = False
    min_date: str | None = None
    max_date: str | None = None

    def _serialize_state(self) -> dict:
        fmt = "YYYY-MM-DDTHH:MM" if self.include_time else "YYYY-MM-DD"
        return self._base_state() | {
            "value": self.value,
            "format": fmt,
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

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        val = data["value"]
        html += f'<p><strong>Value:</strong> {escape(str(val if val is not None else "None"))}</p>'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def _parse(self, body: dict):
        raw = body.get("value", "")
        pattern = DATETIME_RE if self.include_time else DATE_RE
        if not pattern.match(raw):
            fmt = "YYYY-MM-DDTHH:MM" if self.include_time else "YYYY-MM-DD"
            raise ValueError(f"Invalid date format. Expected {fmt}, got: {raw}")
        if self.min_date and raw < self.min_date:
            raise ValueError(f"Date {raw} is before minimum {self.min_date}")
        if self.max_date and raw > self.max_date:
            raise ValueError(f"Date {raw} is after maximum {self.max_date}")
        return raw
