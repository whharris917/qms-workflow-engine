"""
Eigenform Gallery — Interactive tutorial and reference for all 29 eigenform types.

Organized as a tabbed walkthrough from simple to complex. Each section contains
working examples with instructive labels showing off each type's key features.
"""

from engine.eigenforms import TextForm, CheckboxForm
from engine.page import PageForm
from engine.tab import TabForm
from engine.chain import ChainForm
from engine.accordion import AccordionForm
from engine.group import GroupForm
from engine.choice import ChoiceForm
from engine.number import NumberForm
from engine.date import DateForm
from engine.boolean import BooleanForm
from engine.range import RangeForm
from engine.memo import MemoForm
from engine.rating import RatingForm
from engine.rank import RankForm
from engine.multi import MultiForm
from engine.listform import ListForm
from engine.table import TableForm
from engine.keyvalue import KeyValueForm
from engine.visibility import VisibilityForm
from engine.switch import SwitchForm
from engine.dynamic_choice import DynamicChoiceForm
from engine.score import ScoreForm
from engine.computed import ComputedForm
from engine.validation import ValidationForm
from engine.action import ActionForm
from engine.repeater import RepeaterForm
from engine.rubiks import RubiksCubeForm
from engine.multi import FieldDescriptor
from engine.validation import ValidationRule


# ---------------------------------------------------------------------------
# Section 1: Simple Value Forms
# ---------------------------------------------------------------------------

simple_values = GroupForm(
    key="simple-values",
    label="Simple Value Forms",
    instruction=(
        "The building blocks. Each captures a single value and reports "
        "is_complete when that value is set. Try setting each one — the "
        "green border appears when complete."
    ),
    eigenforms=[
        TextForm(
            key="text-demo",
            label="TextForm",
            instruction="The simplest eigenform. Accepts any string. POST {\"value\": \"hello\"} to set it.",
        ),
        NumberForm(
            key="number-demo",
            label="NumberForm",
            instruction=(
                "Numeric input with constraints. This one is clamped to 1-100, "
                "step 0.5, and rounds to float. Try posting a value outside the range."
            ),
            min_val=1,
            max_val=100,
            step=0.5,
        ),
        NumberForm(
            key="integer-demo",
            label="NumberForm (integer mode)",
            instruction="With integer=True, decimal values are truncated. Min 0, max 10.",
            min_val=0,
            max_val=10,
            integer=True,
        ),
        BooleanForm(
            key="boolean-demo",
            label="BooleanForm",
            instruction="Binary toggle. POST {\"value\": \"true\"} or {\"value\": \"false\"}.",
        ),
        BooleanForm(
            key="boolean-custom-demo",
            label="BooleanForm (custom labels)",
            instruction="Same toggle, custom display labels.",
            true_label="Approve",
            false_label="Reject",
        ),
        MemoForm(
            key="memo-demo",
            label="MemoForm",
            instruction="Multi-line textarea. This one requires at least 10 characters and caps at 500.",
            min_length=10,
            max_length=500,
            placeholder="Write something longer than 10 characters...",
        ),
        DateForm(
            key="date-demo",
            label="DateForm",
            instruction="ISO 8601 date. POST {\"value\": \"2026-03-28\"}. Bounded to 2026.",
            min_date="2026-01-01",
            max_date="2026-12-31",
        ),
        DateForm(
            key="datetime-demo",
            label="DateForm (with time)",
            instruction="With include_time=True, accepts YYYY-MM-DDTHH:MM format.",
            include_time=True,
        ),
        RatingForm(
            key="rating-demo",
            label="RatingForm",
            instruction="Ordinal 1-5 rating with custom labels. POST {\"value\": \"4\"} to rate.",
            max_rating=5,
            labels={1: "Terrible", 2: "Poor", 3: "OK", 4: "Good", 5: "Excellent"},
        ),
        RangeForm(
            key="range-demo",
            label="RangeForm",
            instruction="Slider from 0-100%. POST {\"value\": \"75\"} to set. Step is 5.",
            min_val=0,
            max_val=100,
            step=5,
            unit="%",
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 2: Selection Forms
# ---------------------------------------------------------------------------

selection_forms = GroupForm(
    key="selection-forms",
    label="Selection Forms",
    instruction=(
        "Forms for choosing among options. ChoiceForm for single-select, "
        "CheckboxForm for multi-select, RankForm for ordering."
    ),
    eigenforms=[
        ChoiceForm(
            key="choice-demo",
            label="ChoiceForm",
            instruction=(
                "Single selection from a fixed list. "
                "POST {\"value\": \"python\"} to select. "
                "Invalid options are rejected."
            ),
            options=["python", "javascript", "rust", "go"],
        ),
        CheckboxForm(
            key="checkbox-demo",
            label="CheckboxForm",
            instruction=(
                "Multi-select with N/A escape hatch. Check individual items with "
                "{\"item\": \"true\"}, or mark N/A to indicate 'none of these'. "
                "Complete when any item is checked OR N/A is set."
            ),
            items=["Unit Tests", "Integration Tests", "Load Tests", "Manual QA"],
        ),
        RankForm(
            key="rank-demo",
            label="RankForm",
            instruction=(
                "Drag to reorder (via Up/Down buttons) or submit a complete ordering. "
                "POST {\"action\": \"set_order\", \"order\": [\"cost\", \"quality\", \"speed\", \"scope\"]} "
                "to rank all at once. Complete only after an explicit ranking action."
            ),
            items=["cost", "quality", "speed", "scope"],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 3: Multi-Field & Collection Forms
# ---------------------------------------------------------------------------

collection_forms = GroupForm(
    key="collection-forms",
    label="Multi-Field & Collection Forms",
    instruction=(
        "Forms that manage multiple values or dynamic collections. "
        "All collection forms use stable IDs — removing an item never shifts other IDs."
    ),
    eigenforms=[
        MultiForm(
            key="multi-demo",
            label="MultiForm",
            instruction=(
                "Groups several fields into a single affordance. All fields submitted in one POST. "
                "Useful for reducing round-trips when an agent fills related fields together."
            ),
            fields=[
                FieldDescriptor(key="first_name", label="First Name", type="text"),
                FieldDescriptor(key="last_name", label="Last Name", type="text"),
                FieldDescriptor(key="role", label="Role", type="choice",
                                options=["Engineer", "Designer", "Manager", "QA"]),
            ],
        ),
        ListForm(
            key="list-demo",
            label="ListForm",
            instruction=(
                "Ordered list with add/edit/remove/reorder. Supports N/A mode. "
                "Try adding items, then reordering with move up/down. "
                "Item IDs are stable (item_0, item_1, ...) — removing item_1 doesn't renumber item_2."
            ),
        ),
        TableForm(
            key="table-demo",
            label="TableForm",
            instruction=(
                "Dynamic table: add columns first, then rows, then fill cells. "
                "Supports batch actions for filling an entire row at once. "
                "Try: add_column 'Name', add_column 'Score', add_row, set_cell."
            ),
        ),
        KeyValueForm(
            key="kv-demo",
            label="KeyValueForm",
            instruction=(
                "Dynamic key-value pairs with stable entry IDs. "
                "POST {\"action\": \"add\", \"key\": \"color\", \"value\": \"blue\"} to add. "
                "Complete when at least one entry has both key and value."
            ),
            key_label="Property",
            value_label="Setting",
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 4: Container Forms
# ---------------------------------------------------------------------------

container_forms = GroupForm(
    key="container-forms",
    label="Container Forms",
    instruction=(
        "Containers organize eigenforms into navigable structures. "
        "TabForm, ChainForm, and AccordionForm all implement faithful projection — "
        "hidden content is absent from both JSON and HTML."
    ),
    eigenforms=[
        GroupForm(
            key="group-demo",
            label="GroupForm",
            instruction=(
                "The simplest container — just a named group. No tabs, no collapse, "
                "no sequencing. Useful for reusable compositions: define once as a "
                "GroupForm subclass, use in multiple pages."
            ),
            eigenforms=[
                TextForm(key="group-child-1", label="Child 1"),
                TextForm(key="group-child-2", label="Child 2"),
            ],
        ),
        TabForm(
            key="tab-demo",
            label="TabForm",
            instruction=(
                "Tabbed container. Only the active tab appears in JSON and HTML. "
                "Switch tabs with POST {\"tab\": \"second\"}. "
                "Complete when ALL tabs are complete (not just the visible one)."
            ),
            tabs={
                "first": TextForm(
                    key="tab-a",
                    label="First Tab Content",
                    instruction="Fill this, then switch to the second tab.",
                ),
                "second": TextForm(
                    key="tab-b",
                    label="Second Tab Content",
                    instruction="Both tabs must be complete for the TabForm to be complete.",
                ),
            },
        ),
        ChainForm(
            key="chain-demo",
            label="ChainForm",
            instruction=(
                "Sequential wizard. Auto-advances to the first incomplete step. "
                "You can jump back to completed steps and use 'Continue' to resume. "
                "Only the active step is in the output."
            ),
            steps=[
                TextForm(key="step-1", label="Step 1: Your Name", instruction="Fill this to advance."),
                ChoiceForm(
                    key="step-2",
                    label="Step 2: Pick a Color",
                    instruction="Select one to advance to the final step.",
                    options=["red", "green", "blue"],
                ),
                TextForm(key="step-3", label="Step 3: Summary", instruction="Last step. Fill to complete the chain."),
            ],
        ),
        AccordionForm(
            key="accordion-demo",
            label="AccordionForm",
            instruction=(
                "Collapsible sections. Collapsed sections are omitted from JSON and HTML "
                "(faithful projection). Toggle with POST {\"action\": \"toggle\", \"section\": \"basics\"}."
            ),
            sections={
                "basics": TextForm(
                    key="acc-basics",
                    label="Basic Info",
                    instruction="This section starts expanded. Collapse it to hide from output.",
                ),
                "details": TextForm(
                    key="acc-details",
                    label="Additional Details",
                    instruction="Expand this section to interact with it.",
                ),
            },
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 5: Conditional & Dynamic Forms
# ---------------------------------------------------------------------------

# GroupForm subclasses for the SwitchForm demo
class CatProfile(GroupForm):
    pass

class DogProfile(GroupForm):
    pass

conditional_forms = GroupForm(
    key="conditional-forms",
    label="Conditional & Dynamic Forms",
    instruction=(
        "Forms whose structure or options change based on sibling values. "
        "The depends_on parameter names the sibling to watch. "
        "IMPORTANT: the depended-on eigenform must appear BEFORE the dependent."
    ),
    eigenforms=[
        # VisibilityForm demo
        BooleanForm(
            key="show-details",
            label="Show Details?",
            instruction="Toggle this to show/hide the detail field below via VisibilityForm.",
        ),
        VisibilityForm(
            key="vis-demo",
            label="VisibilityForm",
            instruction="This wraps a child and hides it when the condition is false.",
            depends_on="show-details",
            visible_when=True,
            eigenform=MemoForm(
                key="hidden-detail",
                label="Conditional Detail",
                instruction="You can only see (and fill) this when 'Show Details' is True.",
                min_length=5,
            ),
        ),
        # SwitchForm demo
        ChoiceForm(
            key="pet-type",
            label="Pet Type",
            instruction="Select a pet type to see the SwitchForm swap between case subtrees.",
            options=["cat", "dog"],
        ),
        SwitchForm(
            key="switch-demo",
            label="SwitchForm",
            instruction=(
                "N-way switch driven by a sibling value. Each case is a full eigenform subtree. "
                "State is preserved when switching — go back to 'cat' and your answers are still there."
            ),
            depends_on="pet-type",
            cases={
                "cat": CatProfile(
                    key="cat-profile",
                    label="Cat Profile",
                    eigenforms=[
                        TextForm(key="cat-name", label="Cat's Name"),
                        BooleanForm(key="indoor", label="Indoor Cat?"),
                    ],
                ),
                "dog": DogProfile(
                    key="dog-profile",
                    label="Dog Profile",
                    eigenforms=[
                        TextForm(key="dog-name", label="Dog's Name"),
                        ChoiceForm(key="size", label="Size", options=["small", "medium", "large"]),
                    ],
                ),
            },
        ),
        # DynamicChoiceForm demo
        ChoiceForm(
            key="continent",
            label="Continent",
            instruction="Select a continent to see DynamicChoiceForm update its options.",
            options=["Europe", "Asia", "Americas"],
        ),
        DynamicChoiceForm(
            key="dynamic-demo",
            label="DynamicChoiceForm",
            instruction=(
                "Options are computed from a sibling's value. If you change the continent, "
                "your selection becomes 'stale' and you'll need to re-select. "
                "Uses static_options here; options_fn supports arbitrary callables."
            ),
            depends_on="continent",
            static_options={
                "Europe": ["France", "Germany", "Spain", "Italy"],
                "Asia": ["Japan", "India", "China", "Thailand"],
                "Americas": ["Brazil", "Canada", "Mexico", "USA"],
            },
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 6: Computed & Validation Forms
# ---------------------------------------------------------------------------

computed_forms = GroupForm(
    key="computed-forms",
    label="Computed, Scoring & Validation",
    instruction=(
        "Read-only eigenforms that derive display from sibling values. "
        "ScoreForm grades against an answer key. ComputedForm runs arbitrary "
        "functions. ValidationForm enforces cross-field rules."
    ),
    eigenforms=[
        # ScoreForm demo — a mini quiz
        TextForm(
            key="capital-of-france",
            label="What is the capital of France?",
            instruction="Type the answer. ScoreForm below will grade it (case-insensitive).",
        ),
        ChoiceForm(
            key="largest-planet",
            label="What is the largest planet?",
            instruction="Select one.",
            options=["Mars", "Jupiter", "Saturn", "Earth"],
        ),
        ScoreForm(
            key="score-demo",
            label="ScoreForm",
            instruction="Read-only. Grades siblings against the answer key automatically.",
            answer_key={
                "capital-of-france": "Paris",
                "largest-planet": "Jupiter",
            },
        ),
        # ComputedForm demo
        NumberForm(
            key="width",
            label="Width",
            instruction="Enter a width. ComputedForm below will compute the area.",
            min_val=0,
            max_val=1000,
        ),
        NumberForm(
            key="height",
            label="Height",
            instruction="Enter a height.",
            min_val=0,
            max_val=1000,
        ),
        ComputedForm(
            key="computed-demo",
            label="ComputedForm (Area)",
            instruction=(
                "Derived from width * height. Recomputed on every serialize. "
                "With store_result=True, the result is written to the store so "
                "downstream eigenforms (like VisibilityForm) can depend on it."
            ),
            depends_on=["width", "height"],
            compute_fn=lambda vals: (
                vals["width"] * vals["height"]
                if vals.get("width") is not None and vals.get("height") is not None
                else None
            ),
            store_result=True,
        ),
        VisibilityForm(
            key="area-warning",
            label="Large Area Warning",
            depends_on="computed-demo",
            visible_when=lambda val: val is not None and val > 10000,
            eigenform=TextForm(
                key="area-note",
                label="Warning: Large Area",
                instruction="This only appears when width * height > 10,000. Demonstrates ComputedForm + VisibilityForm chaining.",
                default="This area exceeds the recommended maximum.",
            ),
        ),
        # ValidationForm demo
        TextForm(
            key="password",
            label="Password",
            instruction="Enter a password (at least 8 chars for the validation to pass).",
        ),
        TextForm(
            key="confirm-password",
            label="Confirm Password",
            instruction="Must match the password above.",
        ),
        ValidationForm(
            key="validation-demo",
            label="ValidationForm",
            instruction=(
                "Cross-field validation. Rules are pending until dependencies are filled, "
                "then pass or fail. With block_completion=True (default), a failing rule "
                "blocks the parent container's completion."
            ),
            rules=[
                ValidationRule(
                    name="Password length",
                    depends_on=["password"],
                    check_fn=lambda vals: len(vals.get("password", "") or "") >= 8,
                    message="Password must be at least 8 characters.",
                ),
                ValidationRule(
                    name="Passwords match",
                    depends_on=["password", "confirm-password"],
                    check_fn=lambda vals: (
                        vals.get("password") is not None
                        and vals.get("password") == vals.get("confirm-password")
                    ),
                    message="Passwords do not match.",
                ),
            ],
            block_completion=True,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 7: Actions & Repeaters
# ---------------------------------------------------------------------------

def log_action(context, store, scope):
    """Example action function that reads context and writes to store."""
    name = context.get("action-name", "anonymous")
    count = store.get(scope, "__action_count") or 0
    count += 1
    store.set(scope, "__action_count", count)
    return {"message": f"Hello, {name}! This action has been executed {count} time(s)."}


def guarded_action(context, store, scope):
    return {"message": "Access granted. The precondition was satisfied."}


action_forms = GroupForm(
    key="action-forms",
    label="Actions & Repeaters",
    instruction=(
        "ActionForm executes side effects. RepeaterForm stamps a template "
        "for each dynamic entry. Both are key to building real workflows."
    ),
    eigenforms=[
        # Basic ActionForm
        TextForm(
            key="action-name",
            label="Your Name (for the action)",
            instruction="Fill this before clicking Execute below — it's passed as context.",
        ),
        ActionForm(
            key="action-demo",
            label="ActionForm (basic)",
            instruction=(
                "Reads 'action-name' sibling as context, increments a counter in the store, "
                "returns a greeting. The action_fn receives (context, store, scope)."
            ),
            action_label="Say Hello",
            action_fn=log_action,
            depends_on=["action-name"],
        ),
        # ActionForm with precondition + confirmation
        BooleanForm(
            key="agree-terms",
            label="Agree to Terms",
            instruction="Toggle to True to satisfy the precondition for the action below.",
        ),
        ActionForm(
            key="guarded-action-demo",
            label="ActionForm (precondition + confirm)",
            instruction=(
                "This action has two gates: a precondition (agree-terms must be True) "
                "and a two-step confirmation (arm, then confirm or cancel). "
                "Precondition is re-checked at execution time."
            ),
            action_label="Submit",
            action_fn=guarded_action,
            depends_on=["agree-terms"],
            precondition_fn=lambda ctx: ctx.get("agree-terms") is True,
            precondition_message="You must agree to the terms first.",
            confirm=True,
        ),
        # RepeaterForm demo
        RepeaterForm(
            key="repeater-demo",
            label="RepeaterForm",
            instruction=(
                "Stamps a template of eigenforms for each entry. Add entries to see "
                "the template repeated. Each entry gets its own compound scope "
                "(repeater-demo/entry_0, repeater-demo/entry_1, ...). "
                "min_entries=1, max_entries=5 here."
            ),
            template=[
                TextForm(key="item-name", label="Item Name"),
                NumberForm(key="item-qty", label="Quantity", min_val=1, max_val=999, integer=True),
                RatingForm(key="item-priority", label="Priority", max_rating=3,
                           labels={1: "Low", 2: "Medium", 3: "High"}),
            ],
            min_entries=1,
            max_entries=5,
            entry_label="Line Item",
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 8: Showcase
# ---------------------------------------------------------------------------

showcase = GroupForm(
    key="showcase",
    label="Showcase",
    instruction=(
        "Eigenforms can be arbitrarily complex. RubiksCubeForm is a full "
        "Rubik's Cube with face rotations, shuffle, and restart — proving "
        "the protocol scales from simple text inputs to complete interactive applications."
    ),
    eigenforms=[
        RubiksCubeForm(
            key="rubiks-demo",
            label="RubiksCubeForm",
            instruction=(
                "A complete Rubik's Cube. Rotate faces (U/D/L/R/F/B, cw/ccw), "
                "shuffle (20 random moves), or restart. Complete when all faces are solved. "
                "Demonstrates conditional affordances: the 'Restart' button only appears after shuffling."
            ),
        ),
    ],
)


# ---------------------------------------------------------------------------
# Page Definition
# ---------------------------------------------------------------------------

definition = PageForm(
    key="eigenform-gallery",
    label="Eigenform Gallery",
    instruction=(
        "Interactive reference for all 29 eigenform types. Each tab covers a category "
        "with working examples you can interact with. This page IS the documentation."
    ),
    eigenforms=[
        TabForm(
            key="gallery",
            label="Gallery",
            tabs={
                "simple": simple_values,
                "selection": selection_forms,
                "collections": collection_forms,
                "containers": container_forms,
                "conditional": conditional_forms,
                "computed": computed_forms,
                "actions": action_forms,
                "showcase": showcase,
            },
        ),
    ],
)
