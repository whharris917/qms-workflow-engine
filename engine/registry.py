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
    from engine.dictionaryform import DictionaryForm
    from engine.pageform import PageForm
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
    from engine.navigationform import NavigationForm
    from engine.tablerunner import TableRunner
    from engine.historyform import HistoryForm
    from engine.infoform import InfoForm
    r = EigenformRegistry()
    for cls in [
        TextForm, CheckboxForm, ChoiceForm, MultiForm, ListForm, SetForm,
        TableForm, NavigationForm, TableRunner, HistoryForm,
        NumberForm, DateForm, BooleanForm,
        DictionaryForm,
        PageForm, GroupForm, RepeaterForm,
        SwitchForm,
        VisibilityForm, DynamicChoiceForm,
        ScoreForm, ComputedForm, ValidationForm,
        ActionForm, RubiksCubeForm, InfoForm,
    ]:
        r.register(cls)
    # Aliases for the unified NavigationForm modes
    r.register(NavigationForm, name="tab")
    r.register(NavigationForm, name="chain")
    r.register(NavigationForm, name="sequence")
    r.register(NavigationForm, name="accordion")
    # Alias for renamed DictionaryForm
    r.register(DictionaryForm, name="keyvalue")
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
    "steps": "list",         # NavigationForm (all modes)
    "tabs": "dict",          # legacy TabForm descriptors
    "sections": "dict",      # legacy AccordionForm descriptors
    "cases": "dict",         # SwitchForm
    "template": "list",      # RepeaterForm
    "eigenform": "single",   # VisibilityForm
}


def validate_config(type_name: str, config: dict,
                    reg: EigenformRegistry | None = None) -> str | None:
    """Validate config keys against a type's accepted fields.

    Returns None if valid, or an error message string if invalid.
    """
    if reg is None:
        reg = get_registry()
    cls = reg.lookup(type_name)
    if cls is None:
        return f"Unknown type: {type_name}"
    if not config:
        return None

    import dataclasses
    from engine.eigenform import _BASE_FIELDS
    valid_fields = {
        f.name for f in dataclasses.fields(cls)
        if f.name not in _BASE_FIELDS
        and not f.name.startswith("_")
        and f.name not in _CHILD_FIELDS
    }
    invalid = set(config.keys()) - valid_fields
    if invalid:
        return (
            f"Invalid config for {type_name}: {', '.join(sorted(invalid))}. "
            f"Valid config fields: {', '.join(sorted(valid_fields)) or 'none'}"
        )
    return None


def describe_types(reg: EigenformRegistry | None = None) -> dict:
    """Return a description of all registered types and their config fields."""
    if reg is None:
        reg = get_registry()
    import dataclasses
    from engine.eigenform import _BASE_FIELDS
    result = {}
    for name in sorted(reg.available()):
        cls = reg.lookup(name)
        fields = {}
        for f in dataclasses.fields(cls):
            if f.name in _BASE_FIELDS or f.name.startswith("_") or f.name in _CHILD_FIELDS:
                continue
            # Determine type hint string
            type_str = str(f.type) if f.type is not dataclasses.MISSING else "any"
            has_default = f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING
            fields[f.name] = {"type": type_str, "optional": has_default}
        result[name] = {"config": fields}
    return result


# ---------------------------------------------------------------------------
# Type Catalog — categorized type reference for the Add Eigenform UI.
#
# Each category groups related types with one-line descriptions.  Types that
# don't make sense on a mutable page are excluded: page (not embeddable),
# rubikscube (showcase), tablerunner (requires sibling table), and aliases
# (tab/chain/sequence/accordion → use navigation + mode config;
# keyvalue → use dictionary).
# ---------------------------------------------------------------------------

TYPE_CATALOG: list[dict] = [
    {
        "name": "Input",
        "hint": "Collect a single value from the user.",
        "css": "input",
        "types": [
            ("text",     "T",  "Free-form text. Single-line or multiline."),
            ("number",   "#",  "Numeric with min/max/step. Optional slider mode."),
            ("date",     "\u25F7", "Date or datetime with optional bounds."),
            ("boolean",  "\u25D1", "Yes/no toggle with custom labels."),
            ("choice",   "\u25C9", "Single selection from a list of options."),
            ("checkbox", "\u2611", "Multi-select from a list of options."),
            ("multi",    "\u25A4", "Multiple named fields grouped under one form."),
        ],
    },
    {
        "name": "Collections",
        "hint": "Manage ordered lists, sets, or tables of items.",
        "css": "collections",
        "types": [
            ("list",       "\u2630", "Ordered list with add/edit/remove/reorder and ordering constraints."),
            ("set",        "{ }",    "Unordered collection of unique items."),
            ("dictionary", "\u21C4", "Dynamic key-value pairs."),
            ("table",      "\u25A6", "Rows and columns with typed cells, constraints, and reordering."),
        ],
    },
    {
        "name": "Containers",
        "hint": "Organize eigenforms into navigable structures.",
        "css": "containers",
        "types": [
            ("group",      "\u25A2", "Named container for grouping related eigenforms."),
            ("navigation", "\u2B12", "Tabs, wizard chain, gated sequence, or accordion. Set mode in config."),
            ("repeater",   "\u29C9", "Stamps template eigenforms per dynamic entry."),
        ],
    },
    {
        "name": "Reactive",
        "hint": "Conditional behavior, derived values, and validation.",
        "css": "reactive",
        "types": [
            ("switch",        "\u2442", "Selects between subtrees based on a sibling's value."),
            ("visibility",    "\u25D0", "Shows or hides a child based on a condition."),
            ("dynamicchoice", "\u25C8", "Choice whose options depend on a sibling's value."),
            ("computed",      "\u0192", "Read-only value derived from other eigenforms."),
            ("score",         "\u2605", "Auto-grading from an answer key."),
            ("validation",    "\u2713", "Cross-field validation rules (pass/fail)."),
        ],
    },
    {
        "name": "Display & Actions",
        "hint": "Read-only content and imperative triggers.",
        "css": "display",
        "types": [
            ("info",    "\u2139", "Read-only text display. Always complete."),
            ("action",  "\u25B6", "Button with preconditions, confirmation, and side effects."),
            ("history", "\u29D6", "Wraps an eigenform with append-only change history."),
        ],
    },
]


def get_type_catalog() -> list[dict]:
    """Return the canonical type catalog for the Add Eigenform UI.

    Returns a list of category dicts, each with 'name', 'hint', and
    'types' (list of (type_name, description) tuples).
    """
    return TYPE_CATALOG


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

    # Migrate legacy container descriptors to unified NavigationForm
    if type_name in ("tab", "chain", "sequence", "accordion"):
        desc = dict(desc)  # don't mutate the original
        if "tabs" in desc and "steps" not in desc:
            desc["steps"] = list(desc.pop("tabs").values())
        if "sections" in desc and "steps" not in desc:
            desc["steps"] = list(desc.pop("sections").values())
        config = desc.setdefault("config", {})
        if type_name == "tab":
            config.setdefault("mode", "tabs")
        elif type_name == "chain":
            config.setdefault("mode", "chain")
        elif type_name == "sequence":
            config.setdefault("mode", "sequence")
        elif type_name == "accordion":
            config.setdefault("mode", "accordion")
        desc["type"] = type_name = "navigation"

    # If the seed matches at this level, use it (preserves callables)
    if seed is not None and seed.form == type_name and seed.key == key:
        # Apply descriptor overrides that may differ from the seed
        seed.editable = bool(desc.get("editable"))
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
