"""Eigenform Type Registry — explicit mapping from type names to classes.

The registry serves two purposes:

1. **Lookup**: Given a type name string (e.g., "text"), return the
   class (TextForm) so an eigenform can be instantiated at runtime.

2. **Discovery**: Query what types are available, enabling structural
   persistence (Phase C) and structural actions (Phase D) to reference
   eigenforms by name rather than by Python import.

Type names are derived from class names via the same rule as the
Eigenform.form property: strip the "Form" suffix and lowercase.
GroupForm subclasses (e.g., BugReport) register under their own
derived names (e.g., "bugreport"), not under "group".

Usage:
    from engine.registry import registry

    # Auto-registers all built-in eigenform types
    registry.lookup("text")        # -> TextForm
    registry.lookup("rubikscube")  # -> RubiksCubeForm

    # Register a custom GroupForm subclass
    registry.register(BugReport)
    registry.lookup("bugreport")   # -> BugReport

    # Query available types
    registry.available()           # -> ["text", "checkbox", ...]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.eigenforms import Eigenform


def _type_name(cls: type) -> str:
    """Derive the registry name from a class, matching Eigenform.form."""
    return cls.__name__.removesuffix("Form").lower()


class EigenformRegistry:
    """Maps type name strings to eigenform classes."""

    def __init__(self):
        self._types: dict[str, type[Eigenform]] = {}

    def register(self, cls: type[Eigenform], name: str | None = None) -> None:
        """Register an eigenform class.

        If name is not provided, it is derived from the class name
        using the same rule as Eigenform.form.
        """
        key = name if name is not None else _type_name(cls)
        self._types[key] = cls

    def lookup(self, name: str) -> type[Eigenform] | None:
        """Look up an eigenform class by type name. Returns None if not found."""
        return self._types.get(name)

    def available(self) -> list[str]:
        """Return all registered type names, sorted."""
        return sorted(self._types.keys())

    def is_registered(self, name: str) -> bool:
        return name in self._types

    def __contains__(self, name: str) -> bool:
        return name in self._types

    def __len__(self) -> int:
        return len(self._types)

    def __repr__(self) -> str:
        return f"EigenformRegistry({len(self._types)} types)"


def _build_default_registry() -> EigenformRegistry:
    """Create a registry pre-loaded with all built-in eigenform types."""
    # Import here to avoid circular imports at module level
    from engine.eigenforms import TextForm, CheckboxForm
    from engine.choice import ChoiceForm
    from engine.multi import MultiForm
    from engine.listform import ListForm
    from engine.table import TableForm
    from engine.number import NumberForm
    from engine.date import DateForm
    from engine.boolean import BooleanForm
    from engine.memo import MemoForm
    from engine.rating import RatingForm
    from engine.range import RangeForm
    from engine.rank import RankForm
    from engine.keyvalue import KeyValueForm
    from engine.page import PageForm
    from engine.tab import TabForm
    from engine.chain import ChainForm
    from engine.accordion import AccordionForm
    from engine.group import GroupForm
    from engine.repeater import RepeaterForm
    from engine.switch import SwitchForm
    from engine.visibility import VisibilityForm
    from engine.dynamic_choice import DynamicChoiceForm
    from engine.score import ScoreForm
    from engine.computed import ComputedForm
    from engine.validation import ValidationForm
    from engine.action import ActionForm
    from engine.rubiks import RubiksCubeForm

    r = EigenformRegistry()
    for cls in [
        TextForm, CheckboxForm, ChoiceForm, MultiForm, ListForm, TableForm,
        NumberForm, DateForm, BooleanForm, MemoForm, RatingForm, RangeForm,
        RankForm, KeyValueForm,
        PageForm, TabForm, ChainForm, AccordionForm, GroupForm, RepeaterForm,
        SwitchForm,
        VisibilityForm, DynamicChoiceForm,
        ScoreForm, ComputedForm, ValidationForm,
        ActionForm, RubiksCubeForm,
    ]:
        r.register(cls)
    return r


# Module-level default registry, lazily built on first access.
_default: EigenformRegistry | None = None


def get_registry() -> EigenformRegistry:
    """Return the default registry, building it on first call."""
    global _default
    if _default is None:
        _default = _build_default_registry()
    return _default


# Convenience alias — `from engine.registry import registry` triggers the build.
class _RegistryProxy:
    """Lazy proxy so `registry.lookup(...)` works without eager import cycles."""

    def __getattr__(self, name):
        return getattr(get_registry(), name)

    def __contains__(self, item):
        return item in get_registry()

    def __len__(self):
        return len(get_registry())

    def __repr__(self):
        return repr(get_registry())


registry = _RegistryProxy()


# --- Structural reconstruction (Phase C) ---

# Maps descriptor field names to child structure type.
# "list" = list of child descriptors, "dict" = dict of key->descriptor, "single" = one descriptor.
_CHILD_FIELDS = {
    "eigenforms": "list",   # PageForm, GroupForm
    "tabs": "dict",          # TabForm
    "steps": "list",         # ChainForm
    "sections": "dict",      # AccordionForm
    "cases": "dict",         # SwitchForm
    "template": "list",      # RepeaterForm
    "eigenform": "single",   # VisibilityForm
}


def from_descriptor(desc: dict, reg: EigenformRegistry | None = None,
                    seed: "Eigenform | None" = None) -> "Eigenform":
    """Reconstruct an eigenform from a structural descriptor.

    Args:
        desc: descriptor dict produced by to_descriptor()
        reg: registry for type lookup (uses default if None)
        seed: the corresponding seed eigenform from the Python definition.
              If provided and it matches (same type and key), the seed is
              returned directly — preserving any callables that can't be
              serialized. If None, the eigenform is constructed fresh from
              the registry and descriptor config.

    Returns:
        An unbound Eigenform instance ready for bind().
    """
    if reg is None:
        reg = get_registry()

    type_name = desc["type"]
    key = desc["key"]

    # If the seed matches at this level, use it (preserves callables)
    if seed is not None and seed.form == type_name and seed.key == key:
        return seed

    # Construct from registry + descriptor
    cls = reg.lookup(type_name)
    if cls is None:
        raise ValueError(f"Unknown eigenform type: {type_name!r}")

    kwargs = {"key": key, "label": desc.get("label", key)}
    if desc.get("instruction"):
        kwargs["instruction"] = desc["instruction"]

    # Scalar config
    kwargs.update(desc.get("config", {}))

    # Reconstruct children recursively (no seed available for fresh nodes)
    for field_name, child_type in _CHILD_FIELDS.items():
        if field_name not in desc:
            continue
        child_data = desc[field_name]
        if child_type == "list":
            kwargs[field_name] = [from_descriptor(c, reg) for c in child_data]
        elif child_type == "dict":
            kwargs[field_name] = {
                k: from_descriptor(v, reg) for k, v in child_data.items()
            }
        elif child_type == "single":
            kwargs[field_name] = from_descriptor(child_data, reg)

    return cls(**kwargs)
