"""ValidationForm — cross-field validation that reads sibling values and evaluates rules.

A passive, read-only eigenform (like ScoreForm). Evaluates validation rules
on every serialize/render. Rules whose dependencies are not yet filled are
"pending" rather than "failed" — the check function is not invoked.

When block_completion=True (default), the ValidationForm's is_complete
returns False if any rule fails. Since PageForm checks all children,
this blocks page completion until all rules pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any, Callable

from engine.bases import DependentForm
from engine.eigenform import render_dependency_line


@dataclass
class ValidationRule:
    """A single cross-field validation rule."""
    name: str
    depends_on: list[str]
    check_fn: Callable[[dict], bool]
    message: str


@dataclass
class ValidationForm(DependentForm):
    """Evaluates validation rules across sibling eigenform values.

    Rules are evaluated live on every serialize. Each rule reads its
    declared dependencies from the shared store, then invokes check_fn
    with a {key: value} dict. Rules with any None dependency are
    treated as "pending" (not failed).
    """
    rules: list[ValidationRule] = field(default_factory=list)
    block_completion: bool = True

    @property
    def is_complete(self) -> bool:
        if not self.block_completion:
            return True
        results = self._validate()
        return all(r["status"] != "fail" for r in results)

    def _validate(self) -> list[dict]:
        """Evaluate all rules. Returns list of {name, status, message, depends_on}."""
        results = []
        for rule in self.rules:
            values = {}
            pending = False
            for dep_key in rule.depends_on:
                val = self._store.get(self._scope, dep_key) if self._store else None
                values[dep_key] = val
                if val is None:
                    pending = True

            if pending:
                status = "pending"
            elif rule.check_fn(values):
                status = "pass"
            else:
                status = "fail"

            results.append({
                "name": rule.name,
                "status": status,
                "message": rule.message,
                "depends_on": rule.depends_on,
            })
        return results

    def _serialize_state(self) -> dict:
        results = self._validate()
        return self._base_state() | {
            "rules": results,
            "all_valid": all(r["status"] != "fail" for r in results),
        }

    def render_from_data(self, data: dict) -> str:
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        rules = data.get("rules", [])
        if not rules:
            html += '<p style="color: #888;">No validation rules defined.</p>'
            return html

        for r in rules:
            status = r["status"]
            if status == "pass":
                icon = '<span style="color: #2a2;">&#10004;</span>'
                style = "color: #2a2;"
            elif status == "fail":
                icon = '<span style="color: #c22;">&#10008;</span>'
                style = "color: #c22;"
            else:
                icon = '<span style="color: #888;">&#9679;</span>'
                style = "color: #888;"

            html += (
                f'<div style="margin: 4px 0; {style}">'
                f'{icon} <strong>{escape(r["name"])}</strong>'
            )
            if status == "fail":
                html += f' &mdash; {escape(r["message"])}'
            elif status == "pending":
                html += f' &mdash; <em>waiting for input</em>'
            html += f' {render_dependency_line(r.get("depends_on"), self._url_prefix)}'
            html += '</div>'

        return html


