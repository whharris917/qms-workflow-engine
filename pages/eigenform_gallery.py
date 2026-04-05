"""
Eigenform Gallery — Interactive tutorial and reference for all 29 eigenform types.

Organized as a tabbed walkthrough from simple to complex. Each section contains
working examples with instructive labels showing off each type's key features.
"""

from engine.textform import TextForm
from engine.checkboxform import CheckboxForm
from engine.infoform import InfoForm
from engine.pageform import PageForm
from engine.navigationform import NavigationForm
from engine.groupform import GroupForm
from engine.choiceform import ChoiceForm
from engine.numberform import NumberForm
from engine.dateform import DateForm
from engine.booleanform import BooleanForm
from engine.multiform import MultiForm
from engine.listform import ListForm
from engine.setform import SetForm
from engine.tableform import TableForm
from engine.tablerunner import TableRunner
from engine.dictionaryform import DictionaryForm
from engine.visibilityform import VisibilityForm
from engine.switchform import SwitchForm
from engine.dynamicchoiceform import DynamicChoiceForm
from engine.scoreform import ScoreForm
from engine.computedform import ComputedForm
from engine.validationform import ValidationForm
from engine.actionform import ActionForm
from engine.repeaterform import RepeaterForm
from engine.historyform import HistoryForm
from engine.rubikscubeform import RubiksCubeForm
from engine.multiform import FieldDescriptor
from engine.validationform import ValidationRule


# ---------------------------------------------------------------------------
# Section 1: Simple Value Forms
# ---------------------------------------------------------------------------

simple_values = GroupForm(
    key="simple-values",
    label="Simple Value Forms",
    editable=True,
    instruction=(
        "The building blocks of interactive content. Each captures a single "
        "value and reports is_complete when that value is set. Try setting "
        "each one — the green border appears when complete."
    ),
    eigenforms=[
        TextForm(
            key="text-demo",
            label="TextForm",
            instruction="The simplest interactive eigenform. Accepts any string. POST {\"value\": \"hello\"} to set it. This one is editable — click the pencil icon to rename it.",
            editable=True,
        ),
        TextForm(
            key="memo-demo",
            label="TextForm (multiline)",
            instruction="Multi-line textarea. This one requires at least 10 characters and caps at 500.",
            multiline=True,
            min_length=10,
            max_length=500,
            editable=True,
        ),
        NumberForm(
            key="number-demo",
            label="NumberForm",
            instruction=(
                "Numeric input with constraints. This one accepts 1-100, "
                "step 0.5. Out-of-range or invalid-step values are rejected "
                "with a structured error in the feedback banner."
            ),
            min_val=1,
            max_val=100,
            step=0.5,
            editable=True,
        ),
        NumberForm(
            key="range-demo",
            label="NumberForm (slider)",
            instruction="Slider from 0-100%. POST {\"value\": \"75\"} to set. Step is 5.",
            min_val=0,
            max_val=100,
            step=5,
            slider=True,
            unit="%",
            editable=True,
        ),
        BooleanForm(
            key="boolean-demo",
            label="BooleanForm",
            instruction="Binary toggle. POST {\"value\": \"true\"} or {\"value\": \"false\"}.",
            editable=True,
        ),
        BooleanForm(
            key="boolean-custom-demo",
            label="BooleanForm (custom labels)",
            instruction="Same toggle, custom display labels.",
            true_label="Approve",
            false_label="Reject",
            editable=True,
        ),
        DateForm(
            key="date-demo",
            label="DateForm",
            instruction="ISO 8601 date. POST {\"value\": \"2026-03-28\"}. Bounded to 2026.",
            min_date="2026-01-01",
            max_date="2026-12-31",
            editable=True,
        ),
        DateForm(
            key="datetime-demo",
            label="DateForm (with time)",
            instruction="With include_time=True, accepts YYYY-MM-DDTHH:MM format.",
            include_time=True,
            editable=True,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 1b: Static Output
# ---------------------------------------------------------------------------

display_forms = GroupForm(
    key="display-forms",
    label="Display Forms",
    editable=True,
    instruction=(
        "Display-only eigenforms. These show information but don't capture "
        "user input — they're always complete."
    ),
    eigenforms=[
        InfoForm(
            key="info-demo",
            label="InfoForm",
            editable=True,
            text="Read-only text display. No interaction affordances, always complete.\nIn edit mode, an embedded multiline TextForm lets you change the content.",
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 2: Selection Forms
# ---------------------------------------------------------------------------

selection_forms = GroupForm(
    key="selection-forms",
    label="Selection Forms",
    editable=True,
    instruction=(
        "Forms for choosing among options. ChoiceForm for single-select, "
        "CheckboxForm for multi-select."
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
            editable=True,
        ),
        CheckboxForm(
            key="checkbox-demo",
            label="CheckboxForm",
            instruction=(
                "Multi-select with explicit confirmation. Check items, then click Done. "
                "Done with nothing checked means 'none of these apply'. "
                "Changing items after Done requires re-confirmation. "
                "This prevents premature auto-advance in chain mode."
            ),
            items=["Unit Tests", "Integration Tests", "Load Tests", "Manual QA"],
            editable=True,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 3: Multi-Field & Collection Forms
# ---------------------------------------------------------------------------

collection_forms = GroupForm(
    key="collection-forms",
    label="Multi-Field & Collection Forms",
    editable=True,
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
            editable=True,
        ),
        SetForm(
            key="set-demo",
            label="SetForm",
            instruction=(
                "An unordered collection of unique items. Unlike ListForm, there is "
                "no ordering and no duplicate values. Items are added and removed by "
                "value. Try adding 'apple' twice — the duplicate is rejected."
            ),
            editable=True,
        ),
        DictionaryForm(
            key="kv-demo",
            label="DictionaryForm",
            instruction=(
                "Dynamic key-value pairs with stable entry IDs. "
                "POST {\"action\": \"add\", \"key\": \"color\", \"value\": \"blue\"} to add. "
                "Complete when at least one entry has both key and value."
            ),
            key_label="Property",
            value_label="Setting",
            editable=True,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 3b: ListForm Showcase
# ---------------------------------------------------------------------------

list_forms = GroupForm(
    key="list-forms",
    label="ListForm Showcase",
    editable=True,
    instruction=(
        "ListForm is a versatile ordered list with add/edit/remove/reorder. "
        "It supports fixed seed items, ordering constraints, and several "
        "configuration options. Each example below highlights a different use case."
    ),
    eigenforms=[
        ListForm(
            key="list-basic",
            label="Basic List",
            instruction=(
                "A plain list with no constraints. Add items, edit them inline, "
                "reorder with arrows, remove with x. "
                "Item IDs are stable — removing item_1 doesn't renumber item_2."
            ),
            allow_constraints=False,
            editable=True,
        ),
        ListForm(
            key="list-fixed",
            label="Fixed Seed Items",
            instruction=(
                "fixed_items seeds the list with immutable entries (gray background). "
                "They can be reordered but not edited or removed. "
                "User-added items coexist freely alongside them."
            ),
            fixed_items=["Requirements", "Design", "Implementation", "Testing", "Deployment"],
            allow_constraints=False,
            editable=True,
        ),
        ListForm(
            key="list-static-constraints",
            label="Static Ordering Constraints",
            instruction=(
                "must_follow defines ordering rules by item ID. Here, "
                "Implementation (item_2) must follow Design (item_1), "
                "Testing (item_3) must follow Implementation (item_2), "
                "and Deployment (item_4) must follow Testing (item_3). "
                "Move arrows are absent where a move would violate a constraint. "
                "Constraints are ID-based so they survive renames."
            ),
            # item_0=Requirements, item_1=Design, item_2=Implementation,
            # item_3=Testing, item_4=Deployment
            fixed_items=["Requirements", "Design", "Implementation", "Testing", "Deployment"],
            must_follow={
                "item_2": ["item_1"],   # Implementation after Design
                "item_3": ["item_2"],   # Testing after Implementation
                "item_4": ["item_3"],   # Deployment after Testing
            },
            allow_constraints=False,
            editable=True,
        ),
        ListForm(
            key="list-dynamic-constraints",
            label="Dynamic Ordering Constraints",
            instruction=(
                "allow_constraints=True (the default) lets users add and remove "
                "ordering constraints at runtime via the 'Add Constraint' dropdown. "
                "Charlie (item_2) has a built-in constraint requiring it to follow "
                "Alpha (item_0) and Bravo (item_1), shown as '(built-in)'. "
                "Try adding a dynamic constraint, then removing it."
            ),
            # item_0=Alpha, item_1=Bravo, item_2=Charlie, item_3=Delta, item_4=Echo
            fixed_items=["Alpha", "Bravo", "Charlie", "Delta", "Echo"],
            must_follow={"item_2": ["item_0", "item_1"]},  # Charlie after Alpha & Bravo
            editable=True,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 3c: TableForm Showcase
# ---------------------------------------------------------------------------

# Defined here so the TableRunner demo can reference the same instance.
_runner_source_table = TableForm(
    key="table-runner-source",
    label="Runner Source Table",
    instruction=(
        "This table defines a workflow for the TableRunner below. "
        "1) Add rows and name them in the Stage column (authoring-only — not "
        "shown in the runner). 2) Add row constraints to define execution "
        "order. 3) Scroll down to the TableRunner to execute. Only typed "
        "columns (Description, Gate, Complete) appear as interactive "
        "eigenforms in the runner."
    ),
    fixed_columns=[
        "Stage",
        TextForm(key="_tpl", label="Description"),
        ChoiceForm(
            key="_tpl", label="Gate",
            options=["Approval", "Checklist", "Review", "Auto-Pass"],
        ),
        BooleanForm(key="_tpl", label="Complete"),
    ],
    fixed_rows=[
        {"col_0": "Design"},
        {"col_0": "Build"},
        {"col_0": "Test"},
    ],
    row_must_follow={"row_1": ["row_0"], "row_2": ["row_1"]},
)

table_forms = GroupForm(
    key="table-forms",
    label="TableForm Showcase",
    editable=True,
    instruction=(
        "TableForm manages a 2D grid with dynamic columns and rows. Both axes "
        "are backed by OrderedCollection, giving them stable IDs, fixed items, "
        "ordering constraints, and reordering — the same capabilities as ListForm, "
        "applied to rows and columns independently."
    ),
    eigenforms=[
        TableForm(
            key="table-basic",
            label="Basic Table",
            instruction=(
                "Add columns first, then rows, then fill cells inline. "
                "Rows and columns can be reordered with arrow buttons. "
                "Try: add a few columns and rows, then drag data around "
                "by moving rows up/down and columns left/right."
            ),
        ),
        TableForm(
            key="table-fixed-cols",
            label="Fixed Columns",
            instruction=(
                "fixed_columns seeds immutable columns that cannot be renamed "
                "or removed. They can still be reordered. Add rows and fill "
                "in the cells — try removing a column (you can't)."
            ),
            fixed_columns=["Name", "Role", "Status"],
        ),
        TableForm(
            key="table-row-constraints",
            label="Row Ordering Constraints",
            instruction=(
                "allow_row_constraints=True enables per-row prerequisite "
                "dropdowns. Add a constraint to require one row to always "
                "appear after another. Green pills show active constraints. "
                "Move arrows disappear where they would violate a constraint. "
                "Cycles are detected and rejected."
            ),
            allow_row_constraints=True,
        ),
        TableForm(
            key="table-col-constraints",
            label="Column Ordering Constraints",
            instruction=(
                "allow_col_constraints=True enables per-column prerequisite "
                "dropdowns in the header. Blue pills show active constraints. "
                "Try requiring one column to always appear after another, "
                "then try moving it — blocked moves have no arrow button."
            ),
            allow_col_constraints=True,
        ),
        TableForm(
            key="table-full",
            label="Full-Featured Table",
            instruction=(
                "All features enabled: fixed columns, row and column constraints. "
                "The fixed columns (Phase, Owner, Status) cannot be renamed or "
                "removed. Both axes support dynamic ordering constraints."
            ),
            fixed_columns=["Phase", "Owner", "Status"],
            allow_row_constraints=True,
            allow_col_constraints=True,
        ),
        TableForm(
            key="table-typed",
            label="Typed Columns",
            instruction=(
                "Columns can contain eigenforms instead of plain text. Each "
                "cell in a typed column is a bound eigenform instance with its "
                "own state and affordances. Text columns (Task Name) use inline "
                "inputs as usual. Typed columns (Status, Priority, Approved) "
                "render their eigenform widgets inline."
            ),
            fixed_columns=[
                "Task Name",
                ChoiceForm(
                    key="_tpl", label="Status",
                    options=["Not Started", "In Progress", "Done"],
                ),
                ChoiceForm(
                    key="_tpl", label="Priority",
                    options=["Low", "Medium", "High", "Critical"],
                ),
                BooleanForm(key="_tpl", label="Approved"),
            ],
        ),
        _runner_source_table,
        TableRunner(
            key="table-runner-demo",
            label="TableRunner",
            instruction=(
                "A Runner reads a sibling eigenform and presents an execution "
                "interface derived from it. This TableRunner reads the table above "
                "and presents its rows as a gated sequence. Complete each row's "
                "cells to unlock the next. The table's ordering constraints become "
                "execution gates. First, add rows and set constraints in the table "
                "above, then use this runner to execute them sequentially."
            ),
            source=_runner_source_table,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 4: Container Forms
# ---------------------------------------------------------------------------

container_forms = GroupForm(
    key="container-forms",
    label="Container Forms",
    editable=True,
    instruction=(
        "Containers organize eigenforms into navigable structures. "
        "NavigationForm modes (tabs, chain, sequence, accordion) all implement faithful projection — "
        "hidden content is absent from both JSON and HTML."
    ),
    eigenforms=[
        GroupForm(
            key="group-demo",
            label="GroupForm",
            editable=True,
            instruction=(
                "The simplest container — just a named group. No tabs, no collapse, "
                "no sequencing. Useful for reusable compositions: define once as a "
                "GroupForm subclass, use in multiple pages. "
                "Edit mode (pencil icon) enables adding, removing, and reordering "
                "eigenforms within the group."
            ),
            eigenforms=[
                TextForm(key="group-child-1", label="Child 1"),
                TextForm(key="group-child-2", label="Child 2"),
            ],
        ),
        NavigationForm(
            key="tab-demo",
            label="NavigationForm (tabs)",
            mode="tabs",
            editable=True,
            instruction=(
                "Tabbed container. Only the active tab appears in JSON and HTML. "
                "Switch tabs with POST {\"step\": \"tab-b\"}. "
                "Complete when ALL tabs are complete (not just the visible one). "
                "Edit mode (pencil icon) enables adding, removing, and reordering tabs."
            ),
            steps=[
                TextForm(
                    key="tab-a",
                    label="First Tab Content",
                    instruction="Fill this, then switch to the second tab.",
                ),
                TextForm(
                    key="tab-b",
                    label="Second Tab Content",
                    instruction="Both tabs must be complete for the container to be complete.",
                ),
            ],
        ),
        NavigationForm(
            key="chain-demo",
            label="NavigationForm (chain)",
            mode="chain",
            editable=True,
            instruction=(
                "Sequential wizard. Auto-advances to the first incomplete step. "
                "You can jump back to completed steps and use 'Continue' to resume. "
                "Only the active step is in the output. "
                "Edit mode (pencil icon) enables adding, removing, and reordering steps."
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
        NavigationForm(
            key="sequence-demo",
            label="NavigationForm",
            editable=True,
            instruction=(
                "Gated sequential container — like chain mode but without auto-advance. "
                "Complete each step to unlock the next. Use the Back/Next buttons or "
                "click completed steps in the progress bar to navigate. "
                "Locked steps show a lock icon. "
                "Edit mode (pencil icon) enables adding, removing, and reordering steps."
            ),
            steps=[
                TextForm(key="sf-1", label="Step 1: Project Name", instruction="Enter a name to unlock Step 2."),
                ChoiceForm(
                    key="sf-2",
                    label="Step 2: Category",
                    instruction="Select a category to unlock Step 3.",
                    options=["Infrastructure", "Feature", "Bug Fix"],
                ),
                TextForm(key="sf-3", label="Step 3: Description", instruction="Describe the work to complete the sequence."),
            ],
        ),
        NavigationForm(
            key="accordion-demo",
            label="NavigationForm (accordion)",
            mode="accordion",
            editable=True,
            instruction=(
                "Collapsible sections. Collapsed sections are omitted from JSON and HTML "
                "(faithful projection). Toggle with POST {\"action\": \"toggle\", \"step\": \"acc-basics\"}. "
                "Edit mode (pencil icon) enables adding, removing, and reordering sections."
            ),
            steps=[
                TextForm(
                    key="acc-basics",
                    label="Basic Info",
                    instruction="This section starts expanded. Collapse it to hide from output.",
                ),
                TextForm(
                    key="acc-details",
                    label="Additional Details",
                    instruction="Expand this section to interact with it.",
                ),
            ],
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
    editable=True,
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
            editable=True,
        ),
        VisibilityForm(
            key="vis-demo",
            label="VisibilityForm",
            instruction="This wraps a child and hides it when the condition is false.",
            depends_on="show-details",
            visible_when=True,
            eigenform=TextForm(
                key="hidden-detail",
                label="Conditional Detail",
                instruction="You can only see (and fill) this when 'Show Details' is True.",
                multiline=True,
                min_length=5,
            ),
        ),
        # SwitchForm demo
        ChoiceForm(
            key="pet-type",
            label="Pet Type",
            instruction="Select a pet type to see the SwitchForm swap between case subtrees.",
            options=["cat", "dog"],
            editable=True,
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
            editable=True,
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
        # HistoryForm demo
        HistoryForm(
            key="history-demo",
            label="HistoryForm",
            instruction=(
                "Wraps any eigenform with append-only change history. Every change "
                "is recorded with a timestamp. Click 'View History' to browse "
                "previous versions read-only. The history can never be edited or deleted."
            ),
            eigenform=TextForm(
                key="tracked-text",
                label="Tracked Text",
                instruction="Edit this value several times, then view the history to see every change recorded.",
            ),
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 6: Computed & Validation Forms
# ---------------------------------------------------------------------------

computed_forms = GroupForm(
    key="computed-forms",
    label="Computed, Scoring & Validation",
    editable=True,
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
            editable=True,
        ),
        ChoiceForm(
            key="largest-planet",
            label="What is the largest planet?",
            instruction="Select one.",
            options=["Mars", "Jupiter", "Saturn", "Earth"],
            editable=True,
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
            editable=True,
        ),
        NumberForm(
            key="height",
            label="Height",
            instruction="Enter a height.",
            min_val=0,
            max_val=1000,
            editable=True,
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
            editable=True,
        ),
        TextForm(
            key="confirm-password",
            label="Confirm Password",
            instruction="Must match the password above.",
            editable=True,
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
    editable=True,
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
            editable=True,
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
            editable=True,
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
                NumberForm(key="item-qty", label="Quantity", min_val=1, max_val=999, step=1),
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
    editable=True,
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
        "Interactive reference for all 30 eigenform types. Each tab covers a category "
        "with working examples you can interact with. This page IS the documentation."
    ),
    eigenforms=[
        NavigationForm(
            key="gallery",
            label="Gallery",
            mode="tabs",
            editable=True,
            steps=[
                simple_values,
                display_forms,
                selection_forms,
                collection_forms,
                list_forms,
                table_forms,
                container_forms,
                conditional_forms,
                computed_forms,
                action_forms,
                showcase,
            ],
        ),
    ],
)
