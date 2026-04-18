"""SiblingBind — reactive field value derived from another component's state.

Generalizes the DynamicChoiceForm pattern. Any component field that can be
derived from a sibling's stored value can hold a SiblingBind instead of a
literal. At serialize time, the field resolves by looking up the sibling's
current value and applying the bind's callable.

Example::

    from engine.sibling_bind import SiblingBind
    from engine.numberform import NumberForm

    NumberForm(
        key="volume",
        max_val=SiblingBind("tier", lambda t: 1000 if t == "Pro" else 100),
    )

Compared to SiblingRef — which replaces a *key-string* `depends_on` with a
typed reference — SiblingBind replaces a *field value* with a callable over
the referenced sibling's current state. Both participate in bind-time
sibling-existence validation (SiblingBind auto-contributes a SiblingRef to
the declaring component's `_sibling_refs()`).

Reconciliation: a SiblingBind holds a callable, which does not round-trip
through `to_descriptor`. The callable-preservation machinery (`_callable_fields`,
`_missing_callables` warning) applies the same way it does for
`Computation.compute_fn` and `Action.action_fn` — the seed must be present
for the binding to survive reconciliation.
"""

from __future__ import annotations

from typing import Any, Callable

from engine.sibling_ref import SiblingRef


class SiblingBind:
    """A field value that resolves from a sibling's current state at serialize time.

    Args:
        key: the sibling's component key (within the owner's scope).
        fn: callable applied to the sibling's stored value to produce the
            resolved field value. Called with `None` when the sibling has
            no stored value, unless `default` is specified (in which case
            `default` is returned without invoking `fn`).
        expects: optional type assertion on the sibling — same semantics as
            SiblingRef.expects. Validated at bind time.
        default: value returned when the sibling has no stored value.
            Skipping the callable invocation on an unset sibling avoids
            requiring the callable to handle `None` explicitly.
    """

    __slots__ = ("key", "fn", "expects", "default")

    def __init__(
        self,
        key: str,
        fn: Callable[[Any], Any],
        *,
        expects: type | None = None,
        default: Any = None,
    ):
        if not isinstance(key, str) or not key:
            raise ValueError(
                f"SiblingBind requires a non-empty string key, got {key!r}"
            )
        if not callable(fn):
            raise TypeError(
                f"SiblingBind requires a callable fn, got {type(fn).__name__}"
            )
        self.key = key
        self.fn = fn
        self.expects = expects
        self.default = default

    def __repr__(self) -> str:
        parts = [repr(self.key), f"fn={self.fn!r}"]
        if self.expects is not None:
            parts.append(f"expects={self.expects.__name__}")
        if self.default is not None:
            parts.append(f"default={self.default!r}")
        return f"SiblingBind({', '.join(parts)})"

    def resolve(self, sibling_value: Any) -> Any:
        """Resolve to the field value given the sibling's stored value."""
        if sibling_value is None:
            return self.default
        return self.fn(sibling_value)

    def as_sibling_ref(self) -> SiblingRef:
        """Return an equivalent SiblingRef for bind-time validation."""
        return SiblingRef(self.key, expects=self.expects)

    def __deepcopy__(self, memo):
        # Callables are shared, not deep-copied — same approach as Computation's
        # compute_fn (lambdas can't be deepcopied cleanly and don't need to be).
        return SiblingBind(
            self.key, self.fn, expects=self.expects, default=self.default
        )
