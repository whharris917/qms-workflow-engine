"""Component Type Registry — explicit mapping from type names to classes.

The registry serves two purposes:

1. **Lookup**: Given a type name string (e.g., "text"), return the
   class (TextForm) so a component can be instantiated at runtime.

2. **Discovery**: Query what types are available, enabling structural
   persistence (Phase C) and structural actions (Phase D) to reference
   components by name rather than by Python import.

Type names are read from each class's explicit ``form`` class attribute.
Group subclasses (e.g., BugReport) register under their own
form value (e.g., "bugreport"), not under "group".

Usage:
    from engine.registry import registry

    # Auto-registers all built-in component types
    registry.lookup("text")        # -> TextForm
    registry.lookup("rubikscube")  # -> RubiksCubeApp

    # Register a custom Group subclass
    registry.register(BugReport)
    registry.lookup("bugreport")   # -> BugReport

    # Query available types
    registry.available()           # -> ["text", "checkbox", ...]
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.component import Component


def _type_name(cls: type) -> str:
    """Read the registry name from the class's form attribute."""
    return cls.form


class ComponentRegistry:
    """Maps type name strings to component classes."""

    def __init__(self):
        self._types: dict[str, type[Component]] = {}

    def register(self, cls: type[Component], name: str | None = None) -> None:
        """Register a component class.

        If name is not provided, it is read from the class's form attribute.
        """
        key = name if name is not None else _type_name(cls)
        self._types[key] = cls

    def lookup(self, name: str) -> type[Component] | None:
        """Look up a component class by type name. Returns None if not found."""
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
        return f"ComponentRegistry({len(self._types)} types)"


def _build_default_registry() -> ComponentRegistry:
    """Create a registry pre-loaded with all built-in component types."""
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
    from engine.page import Page
    from engine.group import Group
    from engine.repeater import Repeater
    from engine.switch import Switch
    from engine.visibility import Visibility
    from engine.dynamicchoiceform import DynamicChoiceForm
    from engine.score import Score
    from engine.computation import Computation
    from engine.validation import Validation
    from engine.action import Action
    from engine.rubikscubeapp import RubiksCubeApp
    from engine.setform import SetForm
    from engine.navigation import Navigation
    from engine.tablerunner import TableRunner
    from engine.historizer import Historizer
    from engine.infodisplay import InfoDisplay
    r = ComponentRegistry()
    for cls in [
        TextForm, CheckboxForm, ChoiceForm, MultiForm, ListForm, SetForm,
        TableForm, Navigation, TableRunner, Historizer,
        NumberForm, DateForm, BooleanForm,
        DictionaryForm,
        Page, Group, Repeater,
        Switch,
        Visibility, DynamicChoiceForm,
        Score, Computation, Validation,
        Action, RubiksCubeApp, InfoDisplay,
    ]:
        r.register(cls)
    # Aliases for the unified Navigation modes
    r.register(Navigation, name="tab")
    r.register(Navigation, name="chain")
    r.register(Navigation, name="sequence")
    r.register(Navigation, name="accordion")
    # Alias for renamed DictionaryForm
    r.register(DictionaryForm, name="keyvalue")
    return r


# Module-level default registry, lazily built on first access.
_default: ComponentRegistry | None = None


def get_registry() -> ComponentRegistry:
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
    "components": "list",   # Page, Group
    "steps": "list",         # Navigation (all modes)
    "tabs": "dict",          # legacy TabForm descriptors
    "sections": "dict",      # legacy AccordionForm descriptors
    "cases": "dict",         # Switch
    "template": "list",      # Repeater
    "component": "single",   # Visibility
}


def validate_config(type_name: str, config: dict,
                    reg: ComponentRegistry | None = None) -> str | None:
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
    from engine.component import _BASE_FIELDS
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


def describe_types(reg: ComponentRegistry | None = None) -> dict:
    """Return a description of all registered types and their config fields."""
    if reg is None:
        reg = get_registry()
    import dataclasses
    from engine.component import _BASE_FIELDS
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
# Type Catalog — categorized type reference for the Add Component UI.
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
        "hint": "Organize components into navigable structures.",
        "css": "containers",
        "types": [
            ("group",      "\u25A2", "Named container for grouping related components."),
            ("navigation", "\u2B12", "Tabs, wizard chain, gated sequence, or accordion. Set mode in config."),
            ("repeater",   "\u29C9", "Stamps template components per dynamic entry."),
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
            ("computed",      "\u0192", "Read-only value derived from other components."),
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
            ("history", "\u29D6", "Wraps a component with append-only change history."),
        ],
    },
]


def get_type_catalog() -> list[dict]:
    """Return the canonical type catalog for the Add Component UI.

    Returns a list of category dicts, each with 'name', 'hint', and
    'types' (list of (type_name, description) tuples).
    """
    return TYPE_CATALOG


def from_descriptor(desc: dict, reg: ComponentRegistry | None = None,
                    seed: "Component | None" = None) -> "Component":
    """Reconcile a descriptor against a seed to produce a live component.

    This operation is **reconciliation** — the rough equivalent of React's
    element-tree reconciliation. It takes a JSON-serializable descriptor
    (the on-disk source of truth for structure) and an optional Python-side
    seed (the source of truth for callables and other non-serializable
    behavior), and produces an unbound component ready for bind().

    The descriptor wins over seed defaults on scalar fields — the on-disk
    representation is authoritative. The seed wins on callables — they
    cannot round-trip through JSON.

    Args:
        desc: descriptor dict produced by to_descriptor(). Holds type, key,
              label, instruction, editable, optional config, and optional
              children fields.
        reg: registry for type lookup. Uses the default registry if None.
        seed: the corresponding seed component from the Python definition.
              If provided and matching (same type and key), the seed is
              deepcopied and the descriptor's scalars are applied on top —
              preserving callables from the seed. If None or mismatched,
              the component is constructed fresh from the registry and
              descriptor config.

    Returns:
        An unbound Component instance ready for bind().

    Raises:
        ValueError: if desc["type"] is not registered.

    Callable-preservation limitation:
        When a descriptor's type declares callable-valued fields (e.g.,
        Computation.compute, DynamicChoiceForm.options_fn) and the seed
        is absent or does not match by (type, key), the fresh-construction
        path cannot supply the callable. The component reconciles, binds,
        and renders — but the callable behavior is silently dropped. No
        warning is emitted. This is a known limitation; see
        docs/architecture.md §3.3 for mitigations and the planned fix
        (Pass 2 of the framing design plan).

    See also:
        docs/architecture.md §3 — the full reconciliation specification.
        reconcile — alias exported at module level for discoverability.
    """
    if reg is None:
        reg = get_registry()

    type_name = desc["type"]
    key = desc["key"]

    # Migrate legacy container descriptors to unified Navigation
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

    # If the seed matches at this level, use it (preserves callables).
    # Apply the descriptor's scalar fields onto a copy of the seed so the
    # descriptor — the on-disk source of truth — wins over seed defaults.
    if seed is not None and seed.form == type_name and seed.key == key:
        import copy as _copy
        instance = _copy.deepcopy(seed)
        instance._apply_descriptor(desc)
        return instance

    # Construct from registry + descriptor
    cls = reg.lookup(type_name)
    if cls is None:
        raise ValueError(f"Unknown component type: {type_name!r}")

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

    instance = cls(**kwargs)

    # Callable-preservation diagnostic: flag fields that were silently
    # lost because no matching seed was available for deepcopy.
    if cls._callable_fields:
        missing = [f for f in cls._callable_fields
                   if getattr(instance, f, None) is None]
        if missing:
            instance._missing_callables = missing

    return instance


# Discoverability alias. The operation from_descriptor() performs is
# reconciliation in the React sense — walk a descriptor tree, match each
# node against a seed tree by key, deepcopy the matched seed to preserve
# callables, apply the descriptor's scalar overrides, recurse into children.
# Contributors arriving with a React background can find the function
# under either name. See docs/architecture.md §3.
reconcile = from_descriptor
