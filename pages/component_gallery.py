"""
Component Gallery — Interactive tutorial and reference for all 29 component types.

Organized as a tabbed walkthrough from simple to complex. Each section contains
working examples with instructive labels showing off each type's key features.
"""

from engine.textcomponent import TextComponent
from engine.checkboxcomponent import CheckboxComponent
from engine.infocomponent import InfoComponent
from engine.pagecomponent import PageComponent
from engine.navigationcomponent import NavigationComponent
from engine.groupcomponent import GroupComponent
from engine.choicecomponent import ChoiceComponent
from engine.numbercomponent import NumberComponent
from engine.datecomponent import DateComponent
from engine.booleancomponent import BooleanComponent
from engine.multicomponent import MultiComponent
from engine.listcomponent import ListComponent
from engine.setcomponent import SetComponent
from engine.tablecomponent import TableComponent
from engine.tablerunner import TableRunner
from engine.dictionarycomponent import DictionaryComponent
from engine.visibilitycomponent import VisibilityComponent
from engine.switchcomponent import SwitchComponent
from engine.dynamicchoicecomponent import DynamicChoiceComponent
from engine.scorecomponent import ScoreComponent
from engine.computedcomponent import ComputedComponent
from engine.validationcomponent import ValidationComponent
from engine.actioncomponent import ActionComponent
from engine.repeatercomponent import RepeaterComponent
from engine.historycomponent import HistoryComponent
from engine.rubikscubecomponent import RubiksCubeComponent
from engine.multicomponent import FieldDescriptor
from engine.validationcomponent import ValidationRule


# ---------------------------------------------------------------------------
# Section 1: Simple Value Forms
# ---------------------------------------------------------------------------

simple_values = GroupComponent(
    key="simple-values",
    label="Simple Value Forms",
    editable=True,
    instruction=(
        "The building blocks of interactive content. Each captures a single "
        "value and reports is_complete when that value is set. Try setting "
        "each one — the green border appears when complete."
    ),
    components=[
        TextComponent(
            key="text-demo",
            label="TextComponent",
            instruction="The simplest interactive component. Accepts any string. POST {\"value\": \"hello\"} to set it. This one is editable — click the pencil icon to rename it.",
            editable=True,
        ),
        TextComponent(
            key="memo-demo",
            label="TextComponent (multiline)",
            instruction="Multi-line textarea. This one requires at least 10 characters and caps at 500.",
            multiline=True,
            min_length=10,
            max_length=500,
            editable=True,
        ),
        NumberComponent(
            key="number-demo",
            label="NumberComponent",
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
        NumberComponent(
            key="range-demo",
            label="NumberComponent (slider)",
            instruction="Slider from 0-100%. POST {\"value\": \"75\"} to set. Step is 5.",
            min_val=0,
            max_val=100,
            step=5,
            slider=True,
            unit="%",
            editable=True,
        ),
        BooleanComponent(
            key="boolean-demo",
            label="BooleanComponent",
            instruction="Binary toggle. POST {\"value\": \"true\"} or {\"value\": \"false\"}.",
            editable=True,
        ),
        BooleanComponent(
            key="boolean-custom-demo",
            label="BooleanComponent (custom labels)",
            instruction="Same toggle, custom display labels.",
            true_label="Approve",
            false_label="Reject",
            editable=True,
        ),
        DateComponent(
            key="date-demo",
            label="DateComponent",
            instruction="ISO 8601 date. POST {\"value\": \"2026-03-28\"}. Bounded to 2026.",
            min_date="2026-01-01",
            max_date="2026-12-31",
            editable=True,
        ),
        DateComponent(
            key="datetime-demo",
            label="DateComponent (with time)",
            instruction="With include_time=True, accepts YYYY-MM-DDTHH:MM format.",
            include_time=True,
            editable=True,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 1b: Static Output
# ---------------------------------------------------------------------------

display_forms = GroupComponent(
    key="display-forms",
    label="Display Forms",
    editable=True,
    instruction=(
        "Display-only components. These show information but don't capture "
        "user input — they're always complete."
    ),
    components=[
        InfoComponent(
            key="info-demo",
            label="InfoComponent",
            editable=True,
            text="Read-only text display. No interaction affordances, always complete.\nIn edit mode, an embedded multiline TextComponent lets you change the content.",
        ),
    ],
)


# ---------------------------------------------------------------------------
# Section 2: Selection Forms
# ---------------------------------------------------------------------------

selection_forms = GroupComponent(
    key="selection-forms",
    label="Selection Forms",
    editable=True,
    instruction=(
        "Forms for choosing among options. ChoiceComponent for single-select, "
        "CheckboxComponent for multi-select."
    ),
    components=[
        ChoiceComponent(
            key="choice-demo",
            label="ChoiceComponent",
            instruction=(
                "Single selection from a fixed list. "
                "POST {\"value\": \"python\"} to select. "
                "Invalid options are rejected."
            ),
            options=["python", "javascript", "rust", "go"],
            editable=True,
        ),
        CheckboxComponent(
            key="checkbox-demo",
            label="CheckboxComponent",
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

collection_forms = GroupComponent(
    key="collection-forms",
    label="Multi-Field & Collection Forms",
    editable=True,
    instruction=(
        "Forms that manage multiple values or dynamic collections. "
        "All collection forms use stable IDs — removing an item never shifts other IDs."
    ),
    components=[
        MultiComponent(
            key="multi-demo",
            label="MultiComponent",
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
        SetComponent(
            key="set-demo",
            label="SetComponent",
            instruction=(
                "An unordered collection of unique items. Unlike ListComponent, there is "
                "no ordering and no duplicate values. Items are added and removed by "
                "value. Try adding 'apple' twice — the duplicate is rejected."
            ),
            editable=True,
        ),
        DictionaryComponent(
            key="kv-demo",
            label="DictionaryComponent",
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
# Section 3b: ListComponent Showcase
# ---------------------------------------------------------------------------

list_forms = GroupComponent(
    key="list-forms",
    label="ListComponent Showcase",
    editable=True,
    instruction=(
        "ListComponent is a versatile ordered list with add/edit/remove/reorder. "
        "It supports fixed seed items, ordering constraints, and several "
        "configuration options. Each example below highlights a different use case."
    ),
    components=[
        ListComponent(
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
        ListComponent(
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
        ListComponent(
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
        ListComponent(
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
# Section 3c: TableComponent Showcase
# ---------------------------------------------------------------------------

# Defined here so the TableRunner demo can reference the same instance.
_runner_source_table = TableComponent(
    key="table-runner-source",
    label="Runner Source Table",
    instruction=(
        "This table defines a workflow for the TableRunner below. "
        "1) Add rows and name them in the Stage column (authoring-only — not "
        "shown in the runner). 2) Add row constraints to define execution "
        "order. 3) Scroll down to the TableRunner to execute. Only typed "
        "columns (Description, Gate, Complete) appear as interactive "
        "components in the runner."
    ),
    fixed_columns=[
        "Stage",
        TextComponent(key="_tpl", label="Description"),
        ChoiceComponent(
            key="_tpl", label="Gate",
            options=["Approval", "Checklist", "Review", "Auto-Pass"],
        ),
        BooleanComponent(key="_tpl", label="Complete"),
    ],
    fixed_rows=[
        {"col_0": "Design"},
        {"col_0": "Build"},
        {"col_0": "Test"},
    ],
    row_must_follow={"row_1": ["row_0"], "row_2": ["row_1"]},
)

table_forms = GroupComponent(
    key="table-forms",
    label="TableComponent Showcase",
    editable=True,
    instruction=(
        "TableComponent manages a 2D grid with dynamic columns and rows. Both axes "
        "are backed by OrderedCollection, giving them stable IDs, fixed items, "
        "ordering constraints, and reordering — the same capabilities as ListComponent, "
        "applied to rows and columns independently."
    ),
    components=[
        TableComponent(
            key="table-basic",
            label="Basic Table",
            instruction=(
                "Add columns first, then rows, then fill cells inline. "
                "Rows and columns can be reordered with arrow buttons. "
                "Try: add a few columns and rows, then drag data around "
                "by moving rows up/down and columns left/right."
            ),
        ),
        TableComponent(
            key="table-fixed-cols",
            label="Fixed Columns",
            instruction=(
                "fixed_columns seeds immutable columns that cannot be renamed "
                "or removed. They can still be reordered. Add rows and fill "
                "in the cells — try removing a column (you can't)."
            ),
            fixed_columns=["Name", "Role", "Status"],
        ),
        TableComponent(
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
        TableComponent(
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
        TableComponent(
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
        TableComponent(
            key="table-typed",
            label="Typed Columns",
            instruction=(
                "Columns can contain components instead of plain text. Each "
                "cell in a typed column is a bound component instance with its "
                "own state and affordances. Text columns (Task Name) use inline "
                "inputs as usual. Typed columns (Status, Priority, Approved) "
                "render their component widgets inline."
            ),
            fixed_columns=[
                "Task Name",
                ChoiceComponent(
                    key="_tpl", label="Status",
                    options=["Not Started", "In Progress", "Done"],
                ),
                ChoiceComponent(
                    key="_tpl", label="Priority",
                    options=["Low", "Medium", "High", "Critical"],
                ),
                BooleanComponent(key="_tpl", label="Approved"),
            ],
        ),
        _runner_source_table,
        TableRunner(
            key="table-runner-demo",
            label="TableRunner",
            instruction=(
                "A Runner reads a sibling component and presents an execution "
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

container_forms = GroupComponent(
    key="container-forms",
    label="Container Forms",
    editable=True,
    instruction=(
        "Containers organize components into navigable structures. "
        "NavigationComponent modes (tabs, chain, sequence, accordion) all implement faithful projection — "
        "hidden content is absent from both JSON and HTML."
    ),
    components=[
        GroupComponent(
            key="group-demo",
            label="GroupComponent",
            editable=True,
            instruction=(
                "The simplest container — just a named group. No tabs, no collapse, "
                "no sequencing. Useful for reusable compositions: define once as a "
                "GroupComponent subclass, use in multiple pages. "
                "Edit mode (pencil icon) enables adding, removing, and reordering "
                "components within the group."
            ),
            components=[
                TextComponent(key="group-child-1", label="Child 1"),
                TextComponent(key="group-child-2", label="Child 2"),
            ],
        ),
        NavigationComponent(
            key="tab-demo",
            label="NavigationComponent (tabs)",
            mode="tabs",
            editable=True,
            instruction=(
                "Tabbed container. Only the active tab appears in JSON and HTML. "
                "Switch tabs with POST {\"step\": \"tab-b\"}. "
                "Complete when ALL tabs are complete (not just the visible one). "
                "Edit mode (pencil icon) enables adding, removing, and reordering tabs."
            ),
            steps=[
                TextComponent(
                    key="tab-a",
                    label="First Tab Content",
                    instruction="Fill this, then switch to the second tab.",
                ),
                TextComponent(
                    key="tab-b",
                    label="Second Tab Content",
                    instruction="Both tabs must be complete for the container to be complete.",
                ),
            ],
        ),
        NavigationComponent(
            key="chain-demo",
            label="NavigationComponent (chain)",
            mode="chain",
            editable=True,
            instruction=(
                "Sequential wizard. Auto-advances to the first incomplete step. "
                "You can jump back to completed steps and use 'Continue' to resume. "
                "Only the active step is in the output. "
                "Edit mode (pencil icon) enables adding, removing, and reordering steps."
            ),
            steps=[
                TextComponent(key="step-1", label="Step 1: Your Name", instruction="Fill this to advance."),
                ChoiceComponent(
                    key="step-2",
                    label="Step 2: Pick a Color",
                    instruction="Select one to advance to the final step.",
                    options=["red", "green", "blue"],
                ),
                TextComponent(key="step-3", label="Step 3: Summary", instruction="Last step. Fill to complete the chain."),
            ],
        ),
        NavigationComponent(
            key="sequence-demo",
            label="NavigationComponent",
            editable=True,
            instruction=(
                "Gated sequential container — like chain mode but without auto-advance. "
                "Complete each step to unlock the next. Use the Back/Next buttons or "
                "click completed steps in the progress bar to navigate. "
                "Locked steps show a lock icon. "
                "Edit mode (pencil icon) enables adding, removing, and reordering steps."
            ),
            steps=[
                TextComponent(key="sf-1", label="Step 1: Project Name", instruction="Enter a name to unlock Step 2."),
                ChoiceComponent(
                    key="sf-2",
                    label="Step 2: Category",
                    instruction="Select a category to unlock Step 3.",
                    options=["Infrastructure", "Feature", "Bug Fix"],
                ),
                TextComponent(key="sf-3", label="Step 3: Description", instruction="Describe the work to complete the sequence."),
            ],
        ),
        NavigationComponent(
            key="accordion-demo",
            label="NavigationComponent (accordion)",
            mode="accordion",
            editable=True,
            instruction=(
                "Collapsible sections. Collapsed sections are omitted from JSON and HTML "
                "(faithful projection). Toggle with POST {\"action\": \"toggle\", \"step\": \"acc-basics\"}. "
                "Edit mode (pencil icon) enables adding, removing, and reordering sections."
            ),
            steps=[
                TextComponent(
                    key="acc-basics",
                    label="Basic Info",
                    instruction="This section starts expanded. Collapse it to hide from output.",
                ),
                TextComponent(
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

# GroupComponent subclasses for the SwitchComponent demo
class CatProfile(GroupComponent):
    pass

class DogProfile(GroupComponent):
    pass

conditional_forms = GroupComponent(
    key="conditional-forms",
    label="Conditional & Dynamic Forms",
    editable=True,
    instruction=(
        "Forms whose structure or options change based on sibling values. "
        "The depends_on parameter names the sibling to watch. "
        "IMPORTANT: the depended-on component must appear BEFORE the dependent."
    ),
    components=[
        # VisibilityComponent demo
        BooleanComponent(
            key="show-details",
            label="Show Details?",
            instruction="Toggle this to show/hide the detail field below via VisibilityComponent.",
            editable=True,
        ),
        VisibilityComponent(
            key="vis-demo",
            label="VisibilityComponent",
            instruction="This wraps a child and hides it when the condition is false.",
            depends_on="show-details",
            visible_when=True,
            component=TextComponent(
                key="hidden-detail",
                label="Conditional Detail",
                instruction="You can only see (and fill) this when 'Show Details' is True.",
                multiline=True,
                min_length=5,
            ),
        ),
        # SwitchComponent demo
        ChoiceComponent(
            key="pet-type",
            label="Pet Type",
            instruction="Select a pet type to see the SwitchComponent swap between case subtrees.",
            options=["cat", "dog"],
            editable=True,
        ),
        SwitchComponent(
            key="switch-demo",
            label="SwitchComponent",
            instruction=(
                "N-way switch driven by a sibling value. Each case is a full component subtree. "
                "State is preserved when switching — go back to 'cat' and your answers are still there."
            ),
            depends_on="pet-type",
            cases={
                "cat": CatProfile(
                    key="cat-profile",
                    label="Cat Profile",
                    components=[
                        TextComponent(key="cat-name", label="Cat's Name"),
                        BooleanComponent(key="indoor", label="Indoor Cat?"),
                    ],
                ),
                "dog": DogProfile(
                    key="dog-profile",
                    label="Dog Profile",
                    components=[
                        TextComponent(key="dog-name", label="Dog's Name"),
                        ChoiceComponent(key="size", label="Size", options=["small", "medium", "large"]),
                    ],
                ),
            },
        ),
        # DynamicChoiceComponent demo
        ChoiceComponent(
            key="continent",
            label="Continent",
            instruction="Select a continent to see DynamicChoiceComponent update its options.",
            options=["Europe", "Asia", "Americas"],
            editable=True,
        ),
        DynamicChoiceComponent(
            key="dynamic-demo",
            label="DynamicChoiceComponent",
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
        # HistoryComponent demo
        HistoryComponent(
            key="history-demo",
            label="HistoryComponent",
            instruction=(
                "Wraps any component with append-only change history. Every change "
                "is recorded with a timestamp. Click 'View History' to browse "
                "previous versions read-only. The history can never be edited or deleted."
            ),
            component=TextComponent(
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

computed_forms = GroupComponent(
    key="computed-forms",
    label="Computed, Scoring & Validation",
    editable=True,
    instruction=(
        "Read-only components that derive display from sibling values. "
        "ScoreComponent grades against an answer key. ComputedComponent runs arbitrary "
        "functions. ValidationComponent enforces cross-field rules."
    ),
    components=[
        # ScoreComponent demo — a mini quiz
        TextComponent(
            key="capital-of-france",
            label="What is the capital of France?",
            instruction="Type the answer. ScoreComponent below will grade it (case-insensitive).",
            editable=True,
        ),
        ChoiceComponent(
            key="largest-planet",
            label="What is the largest planet?",
            instruction="Select one.",
            options=["Mars", "Jupiter", "Saturn", "Earth"],
            editable=True,
        ),
        ScoreComponent(
            key="score-demo",
            label="ScoreComponent",
            instruction="Read-only. Grades siblings against the answer key automatically.",
            answer_key={
                "capital-of-france": "Paris",
                "largest-planet": "Jupiter",
            },
        ),
        # ComputedComponent demo
        NumberComponent(
            key="width",
            label="Width",
            instruction="Enter a width. ComputedComponent below will compute the area.",
            min_val=0,
            max_val=1000,
            editable=True,
        ),
        NumberComponent(
            key="height",
            label="Height",
            instruction="Enter a height.",
            min_val=0,
            max_val=1000,
            editable=True,
        ),
        ComputedComponent(
            key="computed-demo",
            label="ComputedComponent (Area)",
            instruction=(
                "Derived from width * height. Recomputed on every serialize. "
                "With store_result=True, the result is written to the store so "
                "downstream components (like VisibilityComponent) can depend on it."
            ),
            depends_on=["width", "height"],
            compute_fn=lambda vals: (
                vals["width"] * vals["height"]
                if vals.get("width") is not None and vals.get("height") is not None
                else None
            ),
            store_result=True,
        ),
        VisibilityComponent(
            key="area-warning",
            label="Large Area Warning",
            depends_on="computed-demo",
            visible_when=lambda val: val is not None and val > 10000,
            component=TextComponent(
                key="area-note",
                label="Warning: Large Area",
                instruction="This only appears when width * height > 10,000. Demonstrates ComputedComponent + VisibilityComponent chaining.",
                default="This area exceeds the recommended maximum.",
            ),
        ),
        # ValidationComponent demo
        TextComponent(
            key="password",
            label="Password",
            instruction="Enter a password (at least 8 chars for the validation to pass).",
            editable=True,
        ),
        TextComponent(
            key="confirm-password",
            label="Confirm Password",
            instruction="Must match the password above.",
            editable=True,
        ),
        ValidationComponent(
            key="validation-demo",
            label="ValidationComponent",
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


action_forms = GroupComponent(
    key="action-forms",
    label="Actions & Repeaters",
    editable=True,
    instruction=(
        "ActionComponent executes side effects. RepeaterComponent stamps a template "
        "for each dynamic entry. Both are key to building real workflows."
    ),
    components=[
        # Basic ActionComponent
        TextComponent(
            key="action-name",
            label="Your Name (for the action)",
            instruction="Fill this before clicking Execute below — it's passed as context.",
            editable=True,
        ),
        ActionComponent(
            key="action-demo",
            label="ActionComponent (basic)",
            instruction=(
                "Reads 'action-name' sibling as context, increments a counter in the store, "
                "returns a greeting. The action_fn receives (context, store, scope)."
            ),
            action_label="Say Hello",
            action_fn=log_action,
            depends_on=["action-name"],
        ),
        # ActionComponent with precondition + confirmation
        BooleanComponent(
            key="agree-terms",
            label="Agree to Terms",
            instruction="Toggle to True to satisfy the precondition for the action below.",
            editable=True,
        ),
        ActionComponent(
            key="guarded-action-demo",
            label="ActionComponent (precondition + confirm)",
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
        # RepeaterComponent demo
        RepeaterComponent(
            key="repeater-demo",
            label="RepeaterComponent",
            instruction=(
                "Stamps a template of components for each entry. Add entries to see "
                "the template repeated. Each entry gets its own compound scope "
                "(repeater-demo/entry_0, repeater-demo/entry_1, ...). "
                "min_entries=1, max_entries=5 here."
            ),
            template=[
                TextComponent(key="item-name", label="Item Name"),
                NumberComponent(key="item-qty", label="Quantity", min_val=1, max_val=999, step=1),
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

showcase = GroupComponent(
    key="showcase",
    label="Showcase",
    editable=True,
    instruction=(
        "Components can be arbitrarily complex. RubiksCubeComponent is a full "
        "Rubik's Cube with face rotations, shuffle, and restart — proving "
        "the protocol scales from simple text inputs to complete interactive applications."
    ),
    components=[
        RubiksCubeComponent(
            key="rubiks-demo",
            label="RubiksCubeComponent",
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

definition = PageComponent(
    key="component-gallery",
    label="Component Gallery",
    instruction=(
        "Interactive reference for all 30 component types. Each tab covers a category "
        "with working examples you can interact with. This page IS the documentation."
    ),
    components=[
        NavigationComponent(
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
