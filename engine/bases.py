"""Base classes for eigenform type families.

Each base extracts the shared structural pattern from a family of related
eigenforms. Subclasses override only the parts that differ.

These are not registered in the eigenform registry — only concrete
subclasses are registered. The base classes exist purely to eliminate
code duplication and make the family relationships explicit.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from html import escape
from typing import Any, Callable

from engine.affordances import Affordance, SimpleButtonAffordance, SwitchTabAffordance
from engine.eigenform import Eigenform, render_dependency_line
from engine.store import Store


# ---------------------------------------------------------------------------
# 1. ScalarForm — single typed value
# ---------------------------------------------------------------------------

@dataclass
class ScalarForm(Eigenform):
    """Base for eigenforms that store a single typed value.

    Subclasses provide:
    - _parse(body) -> parsed value (raise ValueError on bad input)
    - get_affordances() — type-specific input affordance
    - _serialize_state() — include type-specific fields
    - render_from_data() — type-specific display (optional; default provided)
    """

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _parse(self, body: dict) -> Any:
        """Parse and validate input from a POST body. Return the value to store.

        Raise ValueError with a user-facing message on invalid input.
        Subclasses must implement.
        """
        raise NotImplementedError

    def _handle(self, body: dict) -> dict:
        try:
            val = self._parse(body)
        except ValueError as e:
            return self._error(str(e), body=body)
        self._store.set(self._scope, self.key, val)
        return self.serialize()

    def _serialize_state(self) -> dict:
        return self._base_state() | {"value": self.value}

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        val = data.get("value")
        html += f'<p><strong>Value:</strong> {escape(str(val if val is not None else "None"))}</p>'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        return html


# ---------------------------------------------------------------------------
# 2. SelectionForm — pick from options
# ---------------------------------------------------------------------------

@dataclass
class SelectionForm(Eigenform):
    """Base for eigenforms that select from a set of options.

    Subclasses provide:
    - current_options property (the live option list)
    - get_affordances() — selection UI
    - _serialize_state() — include options
    """

    @property
    def current_options(self) -> list[str]:
        """The currently valid options. Subclasses must implement."""
        raise NotImplementedError

    @property
    def is_complete(self) -> bool:
        return self.value is not None and self.value in self.current_options

    def _handle(self, body: dict) -> dict:
        value = body.get("value")
        if value in self.current_options:
            self._store.set(self._scope, self.key, value)
            return self.serialize()
        return self._error(f"'{value}' is not a valid option.", body=body)

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        html += f'<p><strong>Selected:</strong> {escape(str(data.get("value") or "None"))}</p>'
        for aff in data.get("affordances", []):
            if not aff.get("_rendered"):
                html += render_affordance_html(aff)
        return html


# ---------------------------------------------------------------------------
# 3. CollectionForm — manage a dynamic set of items
# ---------------------------------------------------------------------------

@dataclass
class CollectionForm(Eigenform):
    """Base for eigenforms that manage a collection of items.

    Subclasses provide the full implementation — this base establishes
    the family relationship and provides a default is_complete.
    """

    @property
    def is_complete(self) -> bool:
        """Default: complete when non-empty. Subclasses may override."""
        return self.value is not None and bool(self.value)


# ---------------------------------------------------------------------------
# 4. SequentialContainer — present children one at a time with gating
# ---------------------------------------------------------------------------

@dataclass
class SequentialContainer(Eigenform):
    """Base for containers that show one child at a time in sequence.

    Subclasses must provide:
    - steps property or field (list of child eigenforms)
    - Navigation-specific affordances and rendering
    """
    steps: list[Eigenform] = field(default_factory=list)

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["steps"] = [ef.to_descriptor() for ef in self.steps]
        return desc

    @property
    def children(self) -> list[Eigenform]:
        return self.steps

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.steps)

    def _bind_children(self, store: Store, url_prefix: str):
        self.steps = [
            ef.bind(store=store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
            for ef in self.steps
        ]

    def _serialize_full(self) -> dict:
        state = self._serialize_state()
        active = self._active_child()
        state["eigenform"] = active.serialize() if active else None
        state["complete"] = self.is_complete
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def _active_child(self) -> Eigenform | None:
        """The currently visible step. Subclasses must implement."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 5. NavigableContainer — children with switchable visibility
# ---------------------------------------------------------------------------

@dataclass
class NavigableContainer(Eigenform):
    """Base for containers where children are in named slots with toggle/switch visibility.

    Subclasses (TabForm, AccordionForm) differ in how many children
    are visible at once and how switching works.
    """

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.children)


# ---------------------------------------------------------------------------
# 6. DependentForm — reads sibling state, produces derived output
# ---------------------------------------------------------------------------

@dataclass
class DependentForm(Eigenform):
    """Base for read-only eigenforms that derive their output from sibling state.

    Subclasses provide _compute() or equivalent, and custom rendering.
    """

    @property
    def has_data(self) -> bool:
        return False  # Computed/derived, not user-entered

    @property
    def is_complete(self) -> bool:
        return True

    def get_affordances(self) -> list[Affordance]:
        return []

    def _handle(self, body: dict) -> dict:
        return self.serialize()


# ---------------------------------------------------------------------------
# 7. WrapperForm — wraps a single child eigenform
# ---------------------------------------------------------------------------

@dataclass
class WrapperForm(Eigenform):
    """Base for eigenforms that wrap a single child and add behavior.

    Subclasses provide the specific wrapping behavior (visibility gating,
    history tracking, N-way routing). The base handles common child
    management: to_descriptor, children property, is_complete delegation.
    """

    @property
    def _wrapped_child(self) -> Eigenform | None:
        """The currently active wrapped child. Subclasses must implement."""
        raise NotImplementedError

    @property
    def children(self) -> list[Eigenform]:
        """All child eigenforms (for traversal). Subclasses must implement."""
        raise NotImplementedError

    @property
    def is_complete(self) -> bool:
        child = self._wrapped_child
        if child is None:
            return True
        return child.is_complete
