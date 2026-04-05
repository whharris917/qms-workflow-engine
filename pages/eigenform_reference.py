"""Eigenform Reference Menu — type documentation for agents.

A read-only reference page that documents all 33 eigenform types:
what they do, when to use them, their config fields, and example
configs. Designed for agent consumption via JSON — an agent can
navigate here before using the Page Builder.

Structure: TabForm (4 category tabs) → AccordionForm (per-type sections)
→ InfoForm (read-only text, one per type).
"""

from engine.accordionform import AccordionForm
from engine.groupform import GroupForm
from engine.infoform import InfoForm
from engine.pageform import PageForm
from engine.tabform import TabForm


def _type_entry(type_name, desc, when, config, example):
    """Build an InfoForm reference entry for one eigenform type."""
    return InfoForm(
        key=f"ref-{type_name}",
        label=type_name,
        text={
            "Description": desc,
            "When to use": when,
            "Config": config,
            "Example": example,
        },
    )


# ---------------------------------------------------------------------------
# Data Forms (14)
# ---------------------------------------------------------------------------

_DATA_FORMS = AccordionForm(
    key="data-types",
    label="Data Forms",
    instruction="14 types that capture values — from simple strings to tables.",
    default_expanded=False,
    sections={
        "text": _type_entry(
            "text",
            "Free-form string input. Single-line by default; set multiline=True for textarea behavior. Optional min_length/max_length validation.",
            "Titles, names, short answers (single-line). Descriptions, paragraphs, long-form text (multiline). The most versatile data eigenform.",
            "default (str, optional): Initial value. multiline (bool, optional): Textarea mode. min_length (int, optional): Minimum characters. max_length (int, optional): Maximum characters. All JSON-configurable.",
            '{"multiline": true, "min_length": 10, "max_length": 500}',
        ),
        "number": _type_entry(
            "number",
            "Numeric input with min/max/step validation. Supports slider UI and unit labels.",
            "Any numeric value. Set slider=True for a range slider with optional unit label. Use step=1 for integer-only input.",
            "min_val (float, optional): Minimum. max_val (float, optional): Maximum. step (float, optional): Increment (use 1 for integers). slider (bool, optional): Render as slider. unit (str, optional): Display unit. All JSON-configurable.",
            '{"min_val": 0, "max_val": 100, "step": 5, "slider": true, "unit": "%"}',
        ),
        "boolean": _type_entry(
            "boolean",
            "Binary yes/no toggle with customizable button labels.",
            "Any true/false choice. Use choice for more than 2 options.",
            "true_label (str, optional): Label for yes button (default: Yes). false_label (str, optional): Label for no button (default: No). JSON-configurable.",
            '{"true_label": "Approve", "false_label": "Reject"}',
        ),
        "choice": _type_entry(
            "choice",
            "Single selection from a list via radio buttons. Complete when one option selected.",
            "Mutually exclusive options. Use checkbox for multi-select, dynamicchoice if options depend on another field.",
            "options (list[str], optional): Available choices. JSON-configurable.",
            '{"options": ["Low", "Medium", "High", "Critical"]}',
        ),
        "checkbox": _type_entry(
            "checkbox",
            "Multi-select checkboxes. Complete when any item checked.",
            "Multiple selections from a fixed set. Use list for user-defined items.",
            "items (list[str], optional): Checkbox labels. JSON-configurable.",
            '{"items": ["Code", "Documentation", "Tests", "Infrastructure"]}',
        ),
        "date": _type_entry(
            "date",
            "ISO 8601 date or datetime picker with optional bounds.",
            "Dates, deadlines, timestamps. Use text if you need a non-standard date format.",
            "include_time (bool, optional): Add time component. min_date (str, optional): Earliest date (ISO 8601). max_date (str, optional): Latest date. JSON-configurable.",
            '{"include_time": true, "min_date": "2026-01-01"}',
        ),
        "list": _type_entry(
            "list",
            "Ordered list with add/edit/remove/reorder. Supports fixed items and ordering constraints.",
            "User-defined ordered collections. Use fixed_items for ranking a known set. Use set for unordered, checkbox for multi-select from fixed options.",
            "fixed_items (list[str], optional): Immutable seed items. must_follow (dict[str, list[str]], optional): Ordering constraints {item: [must_come_after]}. allow_constraints (bool, optional): Show constraint UI. JSON-configurable.",
            '{"fixed_items": ["Setup", "Teardown"], "allow_constraints": true}',
        ),
        "set": _type_entry(
            "set",
            "Unordered collection of unique items. Duplicates rejected.",
            "Tags, categories — where order doesn't matter and uniqueness is enforced. Use list if order matters.",
            "No config fields.",
            "{}",
        ),
        "keyvalue": _type_entry(
            "keyvalue",
            "Dynamic key-value pairs with inline editing. Complete when at least one entry.",
            "Metadata, environment variables, properties — any labeled values. Use multi for a fixed set of named fields.",
            "key_label (str, optional): Column header for keys. value_label (str, optional): Column header for values. JSON-configurable.",
            '{"key_label": "Property", "value_label": "Setting"}',
        ),
        "multi": _type_entry(
            "multi",
            "Groups multiple named fields under a single affordance. Reduces agent round-trips.",
            "Fixed-schema forms (name+email+phone). Use keyvalue for dynamic key-value pairs.",
            "fields (list[FieldDescriptor], optional): Field definitions. Requires Python — FieldDescriptor objects cannot be constructed from JSON config alone.",
            "{}  # Fields must be defined in Python seed",
        ),
        "table": _type_entry(
            "table",
            "Dynamic columns and rows with inline editing, stable IDs, and ordering constraints.",
            "Structured tabular data. Use list for single-column data, keyvalue for two-column data.",
            "fixed_columns (list[str], optional): Initial column names. fixed_rows (list[dict], optional): Pre-populated rows. row_must_follow/col_must_follow (dict, optional): Ordering constraints. allow_row_constraints/allow_col_constraints (bool, optional): Show constraint UI. JSON-configurable.",
            '{"fixed_columns": ["Name", "Role", "Status"]}',
        ),
    },
)


# ---------------------------------------------------------------------------
# Container Forms (8)
# ---------------------------------------------------------------------------

_CONTAINER_FORMS = AccordionForm(
    key="container-types",
    label="Container Forms",
    instruction="8 types that organize and structure other eigenforms.",
    default_expanded=False,
    sections={
        "tab": _type_entry(
            "tab",
            "Tabbed container showing one tab at a time. Faithful projection — only active tab in JSON.",
            "Organizing content into switchable sections. Use accordion if multiple sections should be visible simultaneously.",
            "No config fields. Tabs are added as children (via edit mode or Page Builder structural actions).",
            "{}",
        ),
        "chain": _type_entry(
            "chain",
            "Sequential wizard with auto-advance. Only the first incomplete step is visible.",
            "Step-by-step workflows where the user must complete each step. Use sequence if you want manual Back/Next without auto-advance.",
            "No config fields. Steps are added as children.",
            "{}",
        ),
        "sequence": _type_entry(
            "sequence",
            "Gated sequential container. Steps unlock progressively but require manual Back/Next navigation.",
            "Multi-step flows where the user controls navigation. Use chain for auto-advancing wizards.",
            "No config fields. Steps are added as children.",
            "{}",
        ),
        "accordion": _type_entry(
            "accordion",
            "Collapsible sections. Multiple sections can be expanded simultaneously. Collapsed sections omitted from JSON.",
            "Reference material, FAQs, grouped content where multiple sections may be relevant at once. Use tab for exclusive one-at-a-time viewing.",
            "No config fields. Sections are added as children.",
            "{}",
        ),
        "group": _type_entry(
            "group",
            "Named container for reusable eigenform compositions. Supports parameterization via subclassing.",
            "Grouping related fields that appear together (e.g., an address block). Use page for top-level containers.",
            "No config fields. Children are added as eigenforms.",
            "{}",
        ),
        "visibility": _type_entry(
            "visibility",
            "Wraps a child with conditional visibility based on a sibling's value.",
            "Showing/hiding fields based on another field's state. Use switch for N-way structural selection.",
            "depends_on (str, optional): Key of sibling eigenform to watch. visible_when (any, optional): Value, list of values, or callable that controls visibility. Value/list are JSON-configurable; callable requires Python.",
            '{"depends_on": "priority", "visible_when": "Critical"}',
        ),
        "switch": _type_entry(
            "switch",
            "N-way structural selection based on sibling value. Each case is a different eigenform subtree.",
            "Showing entirely different form structures based on a choice (e.g., Bug Report vs Feature Request). Use visibility for simple show/hide.",
            "depends_on (str, optional): Key of sibling eigenform to switch on. JSON-configurable. Cases are added as children, keyed by the sibling's value.",
            '{"depends_on": "ticket_type"}',
        ),
        "page": _type_entry(
            "page",
            "Top-level container and persistence boundary. Owns a Store backed by a JSON file.",
            "Rarely added dynamically — pages are usually defined as seeds. Use group for nested containers.",
            "mutable_structure (bool, optional): Allow runtime add/remove/reorder of children. JSON-configurable.",
            '{"mutable_structure": true}',
        ),
    },
)


# ---------------------------------------------------------------------------
# Reactive Forms (4)
# ---------------------------------------------------------------------------

_REACTIVE_FORMS = AccordionForm(
    key="reactive-types",
    label="Reactive Forms",
    instruction="4 types that read sibling values — for scoring, computation, validation, and dynamic options.",
    default_expanded=False,
    sections={
        "score": _type_entry(
            "score",
            "Read-only grading from an answer key. Compares sibling values against expected answers.",
            "Quiz scoring, automated grading. Use computed for arbitrary derived values.",
            "answer_key (dict[str, any], optional): Map of sibling_key to expected_value. JSON-configurable.",
            '{"answer_key": {"q1": "Paris", "q2": "H2O", "q3": "1969"}}',
        ),
        "computed": _type_entry(
            "computed",
            "Read-only derived display from sibling values. Optional store_result for cross-eigenform dependencies.",
            "Totals, summaries, derived metrics. Use score for answer-key grading.",
            "depends_on (list[str], optional): Sibling keys to read. JSON-configurable. compute_fn (callable, optional): Derivation function. Requires Python. store_result (bool, optional): Persist result for use by other eigenforms. display_format (str, optional): Format string. JSON-configurable.",
            '{"depends_on": ["price", "quantity"], "store_result": true}  # compute_fn requires Python',
        ),
        "validation": _type_entry(
            "validation",
            "Cross-field validation rules. Pending/pass/fail status. Can block page completion.",
            "Enforcing relationships between fields (e.g., end_date > start_date). Cannot be fully configured via JSON.",
            "rules (list[ValidationRule], optional): Validation rules with check_fn. Requires Python. block_completion (bool, optional): Whether failures block page completion. JSON-configurable.",
            '{"block_completion": true}  # rules require Python',
        ),
        "dynamicchoice": _type_entry(
            "dynamicchoice",
            "Choice whose options depend on a sibling's value. Detects stale selections.",
            "Dependent dropdowns (country → city). Use choice for static options.",
            "depends_on (str, optional): Sibling key to read. JSON-configurable. static_options (dict[any, list[str]], optional): Map of sibling_value to options list. JSON-configurable. options_fn (callable, optional): Dynamic function. Requires Python.",
            '{"depends_on": "country", "static_options": {"US": ["NYC", "LA", "Chicago"], "UK": ["London", "Manchester"]}}',
        ),
    },
)


# ---------------------------------------------------------------------------
# Actions & Special (5)
# ---------------------------------------------------------------------------

_SPECIAL_FORMS = AccordionForm(
    key="special-types",
    label="Actions & Special",
    instruction="5 types for imperative actions, dynamic repetition, change tracking, workflow execution, and showcase.",
    default_expanded=False,
    sections={
        "action": _type_entry(
            "action",
            "Imperative button with preconditions, confirmation, and side effects. Can return structural_actions to reshape the page.",
            "Submit buttons, generate actions, any imperative operation. Core logic requires Python callables.",
            "action_label (str, optional): Button text. JSON-configurable. confirm (bool, optional): Require confirmation. JSON-configurable. depends_on (list[str], optional): Sibling keys for preconditions. JSON-configurable. action_fn (callable): Side-effect function. Requires Python. precondition_fn (callable, optional): Guard function. Requires Python. precondition_message (str, optional): Failure message. JSON-configurable.",
            '{"action_label": "Submit", "confirm": true}  # action_fn requires Python',
        ),
        "repeater": _type_entry(
            "repeater",
            "Stamps template eigenforms per dynamic entry. Each entry gets its own scope and stable ID.",
            "Repeated form sections (multiple addresses, line items). Children define the template stamped per entry.",
            "min_entries (int, optional): Minimum entries. max_entries (int, optional): Maximum entries. entry_label (str, optional): Label template. JSON-configurable.",
            '{"min_entries": 1, "max_entries": 10, "entry_label": "Item"}',
        ),
        "history": _type_entry(
            "history",
            "Wraps an eigenform with append-only change history. Lazy detection — compares child state to last snapshot.",
            "Audit trails, change tracking. Wraps exactly one child eigenform.",
            "No config fields. The wrapped eigenform is added as a child.",
            "{}",
        ),
        "tablerunner": _type_entry(
            "tablerunner",
            "Reads a sibling TableForm and presents its rows as a gated sequential workflow. Only typed columns are executable.",
            "Executing a table of tasks as a step-by-step workflow. The source TableForm must exist as a sibling.",
            "source (str, optional): Key of sibling TableForm to read. JSON-configurable.",
            '{"source": "task-table"}',
        ),
        "rubikscube": _type_entry(
            "rubikscube",
            "Full Rubik's Cube with face rotations and conditional affordances based on solved state.",
            "Complexity showcase. Not typically used in production pages.",
            "No config fields.",
            "{}",
        ),
    },
)


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

_OVERVIEW = GroupForm(
    key="overview",
    label="Overview",
    eigenforms=[
        InfoForm(
            key="what-are-eigenforms",
            label="What are eigenforms?",
            text={
                "Concept": (
                    "An eigenform is a self-contained interactive unit — it holds state, "
                    "serializes itself to JSON, renders itself to HTML, and exposes "
                    "affordances (actions you can take via POST requests). Each eigenform "
                    "is a small HATEOAS-compliant application: the JSON response tells you "
                    "everything you can do next."
                ),
                "Identity": (
                    "The name comes from eigenvector — an eigenform preserves its identity "
                    "under transformation. Serialize it, store it, reconstruct it from a "
                    "descriptor — it's still the same eigenform with the same behavior."
                ),
                "Completeness": (
                    "Every eigenform has an is_complete property. A TextForm is complete "
                    "when it has a value. A ChainForm is complete when all its steps are "
                    "complete. Pages are complete when all their children are complete. "
                    "This gives you progress tracking for free at every level."
                ),
            },
        ),
        InfoForm(
            key="composition-model",
            label="How composition works",
            text={
                "Pages and children": (
                    "A PageForm is the top-level container. It holds a list of eigenforms "
                    "as children. Children can be data forms (TextForm, NumberForm, etc.) "
                    "or containers (TabForm, ChainForm, AccordionForm) that hold their own "
                    "children. You build pages by nesting eigenforms to any depth."
                ),
                "Containers": (
                    "Containers give structure: TabForm shows one child at a time (tabs), "
                    "ChainForm shows children sequentially (wizard), AccordionForm shows "
                    "collapsible sections, SequenceForm gates progression. Containers are "
                    "composable — a TabForm can hold a ChainForm, which holds data forms."
                ),
                "Sibling communication": (
                    "Some eigenforms read sibling values: ScoreForm grades against an "
                    "answer key, ComputedForm derives values, ValidationForm checks cross-field "
                    "rules, DynamicChoiceForm changes options based on a sibling, SwitchForm "
                    "selects between subtrees, and VisibilityForm shows/hides children. These "
                    "use a depends_on config pointing to a sibling's key."
                ),
            },
        ),
        InfoForm(
            key="building-workflows",
            label="Building workflows and pages",
            text={
                "Simple form": (
                    "A simple form is a PageForm with data eigenforms as children. "
                    "Example: a bug report with TextForm (title), ChoiceForm (severity), "
                    "TextForm(multiline=True) (description), CheckboxForm (affected areas)."
                ),
                "Multi-step workflow": (
                    "A multi-step workflow uses ChainForm or SequenceForm to gate "
                    "progression. Wrap each phase in a GroupForm inside a ChainForm. "
                    "The user completes one step before seeing the next."
                ),
                "Conditional structure": (
                    "Use SwitchForm to show different form structures based on a choice. "
                    "Example: a ChoiceForm (ticket type) with a SwitchForm that depends on "
                    "it — selecting 'Bug' shows bug-specific fields, 'Feature' shows "
                    "feature-specific fields."
                ),
                "Dynamic pages": (
                    "Mutable pages (mutable_structure=True on PageForm) let users add, "
                    "remove, and reorder eigenforms at runtime. The Page Builder is a "
                    "mutable page. ActionForm can return structural_actions to reshape "
                    "the page programmatically."
                ),
            },
        ),
        InfoForm(
            key="config-and-json",
            label="Config and JSON configurability",
            text={
                "What config is": (
                    "Each eigenform type has config fields — parameters that control its "
                    "behavior. When adding an eigenform via the Page Builder, you pass a "
                    "config dict with these fields. Example: NumberForm accepts "
                    '{\"min_val\": 0, \"max_val\": 100, \"step\": 1}.'
                ),
                "JSON vs Python": (
                    "Some config fields accept Python callables (functions) that cannot be "
                    "expressed in JSON. These are marked 'Requires Python' in the type "
                    "reference tabs. Types with callable-only configs (ComputedForm, "
                    "ValidationForm, ActionForm) can still be added via JSON but will have "
                    "limited functionality until their Python seed defines the callable."
                ),
                "Containers need children": (
                    "Container types (TabForm, ChainForm, AccordionForm, GroupForm, etc.) "
                    "have no meaningful config — their value comes from the children nested "
                    "inside them. After adding a container, add children to it using its "
                    "own structural affordances (Add Tab, Add Step, etc.)."
                ),
            },
        ),
    ],
)


# ---------------------------------------------------------------------------
# Page definition
# ---------------------------------------------------------------------------

definition = PageForm(
    key="eigenform-reference",
    label="Eigenform Reference Menu",
    instruction=(
        "Reference guide for all eigenform types. Start with the Overview tab "
        "for concepts and composition patterns, then switch to a type category "
        "tab and expand any section for details."
    ),
    eigenforms=[
        TabForm(
            key="categories",
            label="Type Categories",
            tabs={
                "overview": _OVERVIEW,
                "data": _DATA_FORMS,
                "containers": _CONTAINER_FORMS,
                "computed": _REACTIVE_FORMS,
                "special": _SPECIAL_FORMS,
            },
        ),
    ],
)
