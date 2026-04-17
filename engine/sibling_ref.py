"""SiblingRef — typed reference to a sibling component.

Replaces string-typed `depends_on="key"` with a validatable value that still
behaves as a string for all existing call sites. See docs/architecture.md §2
(Keys and scope) and the framing design plan (Pass 2, Move 1) for rationale.

Design: SiblingRef IS-A str. It is the sibling's key, with an optional
`.expects` type assertion attached. All existing code that treats
`depends_on` as a string (URL composition, store lookups, JSON serialization,
`render_dependency_line`) keeps working without modification — SiblingRef
passes every `isinstance(x, str)` check. The only new behavior is the
`.expects` attribute, used by PageComponent at bind time to validate that the
referenced sibling exists and (optionally) has the expected type.

Usage in seed files:
    # Plain string — no type assertion:
    VisibilityComponent(key="advanced", depends_on="mode", ...)

    # With type assertion — validated at bind time:
    from engine.textcomponent import TextComponent
    ComputedComponent(key="summary", depends_on=[SiblingRef("name", expects=TextComponent)], ...)

Either form works; the plain-string form is auto-coerced by the owning
component's __post_init__.
"""

from __future__ import annotations

from typing import Iterable


class SiblingRef(str):
    """A sibling component reference.

    Behaves as a string (the sibling's key) with an optional `.expects`
    type assertion attached. Two SiblingRefs with the same key compare equal
    regardless of `.expects`; a SiblingRef compares equal to its key string.

    Args:
        key: the sibling's component key (unique within the shared scope).
             Must be a non-empty string.
        expects: optional class to assert the sibling is an instance of.
                 When set, bind-time validation fails if the referenced
                 sibling is of a different type. Use for contracts like
                 "this ComputedComponent expects its dependency to be a TextComponent."
    """

    __slots__ = ("_expects",)

    def __new__(cls, key: str, expects: type | None = None):
        if not isinstance(key, str) or not key:
            raise ValueError(
                f"SiblingRef requires a non-empty string key, got {key!r}"
            )
        inst = super().__new__(cls, key)
        inst._expects = expects
        return inst

    # str subclasses must implement __reduce__ for copy.deepcopy to work
    # correctly when extra attributes (like _expects) are attached.
    def __reduce__(self):
        return (self.__class__, (str(self), self._expects))

    def __repr__(self) -> str:
        if self._expects is not None:
            return f"SiblingRef({str(self)!r}, expects={self._expects.__name__})"
        return f"SiblingRef({str(self)!r})"

    @property
    def key(self) -> str:
        """The sibling's key, as a plain str (for when isinstance checks are
        needed elsewhere in the codebase)."""
        return str(self)

    @property
    def expects(self) -> type | None:
        """The optional type assertion, or None if unconstrained."""
        return self._expects

    @classmethod
    def coerce(cls, value) -> "SiblingRef":
        """Accept either a plain string or a SiblingRef; return a SiblingRef."""
        if isinstance(value, SiblingRef):
            return value
        if isinstance(value, str):
            return cls(value)
        raise TypeError(
            f"Expected str or SiblingRef for sibling reference, "
            f"got {type(value).__name__}: {value!r}"
        )

    @classmethod
    def coerce_many(cls, values: Iterable) -> list["SiblingRef"]:
        """Coerce a sequence of strings / SiblingRefs into a list of SiblingRefs."""
        return [cls.coerce(v) for v in values]


class SiblingRefError(ValueError):
    """Raised when a SiblingRef cannot be resolved at bind time.

    Attributes:
        owner_key: the key of the component that declared the ref.
        owner_scope: the scope in which the ref was searched.
        ref: the SiblingRef that failed to resolve.
        known_keys: the sibling keys that DO exist in the scope, for
                    diagnostic messages.
        reason: one of "missing", "type_mismatch".
    """

    def __init__(self, owner_key: str, owner_scope: str,
                 ref: SiblingRef, known_keys: list[str], reason: str,
                 actual_type: type | None = None):
        self.owner_key = owner_key
        self.owner_scope = owner_scope
        self.ref = ref
        self.known_keys = known_keys
        self.reason = reason
        self.actual_type = actual_type
        keys_str = ", ".join(repr(k) for k in known_keys) if known_keys else "(none)"
        if reason == "type_mismatch" and ref.expects is not None and actual_type is not None:
            msg = (
                f"SiblingRef({ref.key!r}, expects={ref.expects.__name__}) "
                f"declared by {owner_key!r} in scope {owner_scope!r} resolved "
                f"to a sibling of type {actual_type.__name__}, not "
                f"{ref.expects.__name__}."
            )
        else:
            msg = (
                f"SiblingRef({ref.key!r}) declared by {owner_key!r} in scope "
                f"{owner_scope!r} could not be resolved: no sibling with that "
                f"key exists. Known sibling keys: {keys_str}."
            )
        super().__init__(msg)
