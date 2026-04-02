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
from typing import Any, Callable

from engine.eigenform import Eigenform
from engine.templates import render_template


@dataclass
class ValidationRule:
    """A single cross-field validation rule."""
    name: str
    depends_on: list[str]
    check_fn: Callable[[dict], bool]
    message: str


@dataclass
class ValidationForm(Eigenform):
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

    def get_affordances(self):
        return []

    def render_from_data(self, data: dict) -> str:
        return render_template("validation.html", data=data, ef=self,
                               url_prefix=self._url_prefix)

    def _handle(self, body: dict) -> dict:
        return self.serialize()
