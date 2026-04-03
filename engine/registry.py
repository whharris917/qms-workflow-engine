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
    from engine.eigenform import Eigenform


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
    from engine.textform import TextForm
    from engine.checkboxform import CheckboxForm
    from engine.choiceform import ChoiceForm
    from engine.multiform import MultiForm
    from engine.listform import ListForm
    from engine.tableform import TableForm
    from engine.numberform import NumberForm
    from engine.dateform import DateForm
    from engine.booleanform import BooleanForm
    from engine.memoform import MemoForm
    from engine.rangeform import RangeForm
    from engine.rankform import RankForm
    from engine.keyvalueform import KeyValueForm
    from engine.pageform import PageForm
    from engine.tabform import TabForm
    from engine.chainform import ChainForm
    from engine.accordionform import AccordionForm
    from engine.groupform import GroupForm
    from engine.repeaterform import RepeaterForm
    from engine.switchform import SwitchForm
    from engine.visibilityform import VisibilityForm
    from engine.dynamicchoiceform import DynamicChoiceForm
    from engine.scoreform import ScoreForm
    from engine.computedform import ComputedForm
    from engine.validationform import ValidationForm
    from engine.actionform import ActionForm
    from engine.rubikscubeform import RubiksCubeForm
    from engine.setform import SetForm
    from engine.stepform import SequenceForm
    from engine.tablerunner import TableRunner
    from engine.historyform import HistoryForm
    from engine.listformx import ListFormX
    from engine.tableformx import TableFormX
    from engine.choiceformx import ChoiceFormX
    from engine.checkboxformx import CheckboxFormX
    from engine.numberformx import NumberFormX
    from engine.booleanformx import BooleanFormX
    from engine.memoformx import MemoFormX
    from engine.tabformx import TabFormX
    from engine.accordionformx import AccordionFormX

    r = EigenformRegistry()
    for cls in [
        TextForm, CheckboxForm, ChoiceForm, MultiForm, ListForm, SetForm,
        TableForm, SequenceForm, TableRunner, HistoryForm,
        NumberForm, DateForm, BooleanForm, MemoForm, RangeForm,
        RankForm, KeyValueForm,
        PageForm, TabForm, ChainForm, AccordionForm, GroupForm, RepeaterForm,
        SwitchForm,
        VisibilityForm, DynamicChoiceForm,
        ScoreForm, ComputedForm, ValidationForm,
        ActionForm, RubiksCubeForm, ListFormX, TableFormX,
        ChoiceFormX, CheckboxFormX,
        NumberFormX, BooleanFormX, MemoFormX, TabFormX, AccordionFormX,
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
    if desc.get("editable"):
        kwargs["editable"] = True

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
