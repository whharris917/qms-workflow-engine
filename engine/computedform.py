"""ComputedForm — read-only derived display computed from sibling state.

Generalizes ScoreForm's sibling-reading pattern for arbitrary computations.
The compute function receives a dict of sibling values and returns any
JSON-serializable result.

When store_result=True, the computed value is written to the store during
serialization, enabling VisibilityForm and other sibling-readers to depend
on the result. This is idempotent — every serialize recomputes.

ORDERING: When store_result=True, this eigenform must appear BEFORE any
VisibilityForm that depends on its stored result in the parent's children
list, since PageForm serializes children in list order.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from engine.eigenform import Eigenform
from engine.sibling_ref import SiblingRef
from engine.templates import render_template


@dataclass
class ComputedForm(Eigenform):
    """Read-only eigenform that computes a value from sibling state."""
    depends_on: "list[str | SiblingRef]" = field(default_factory=list)
    compute_fn: Callable[[dict], Any] | None = None
    store_result: bool = False
    display_format: str | None = None

    def __post_init__(self):
        if self.depends_on:
            self.depends_on = SiblingRef.coerce_many(self.depends_on)

    def _sibling_refs(self) -> list[SiblingRef]:
        return [r for r in self.depends_on if isinstance(r, SiblingRef)]

    @property
    def has_data(self) -> bool:
        return False  # Computed, not user-entered

    @property
    def is_complete(self) -> bool:
        return True

    def _gather_siblings(self) -> dict:
        values = {}
        for dep_key in self.depends_on:
            values[dep_key] = self._store.get(self._scope, dep_key) if self._store else None
        return values

    def _compute(self) -> Any:
        siblings = self._gather_siblings()
        if self.compute_fn:
            return self.compute_fn(siblings)
        return siblings

    def _serialize_state(self) -> dict:
        computed = self._compute()
        if self.store_result and self._store:
            self._store.set(self._scope, self.key, computed)
        return self._base_state() | {
            "computed_value": computed,
            "depends_on": self.depends_on,
            "display_format": self.display_format,
        }

    def get_affordances(self):
        return []

    def render_from_data(self, data: dict) -> str:
        return render_template("computed.html", data=data, ef=self,
                               url_prefix=self._url_prefix)

    def _handle(self, body: dict) -> dict:
        return self.serialize()
