"""Weird Experiments — a playground for unconventional eigenform compositions.

Exercises all four new eigenform capabilities:
- ValidationForm: cross-field validation (date ordering, number comparison)
- DynamicChoiceForm: options that depend on a sibling's value
- ActionForm: imperative button with preconditions and side effects
- RepeaterForm: dynamic repeated structure from a template
"""

from math import prod

from engine.actionform import ActionForm
from engine.choiceform import ChoiceForm
from engine.computedform import ComputedForm
from engine.dateform import DateForm
from engine.dynamicchoiceform import DynamicChoiceForm
from engine.checkboxform import CheckboxForm
from engine.textform import TextForm
from engine.numberform import NumberForm
from engine.pageform import PageForm
from engine.repeaterform import RepeaterForm
from engine.store import Store
from engine.validationform import ValidationForm, ValidationRule


# --- Experiment 1: Number multiplier (existing) ---

def multiply_selected(siblings):
    checked = siblings.get("numbers")
    if not checked:
        return {"status": "incomplete", "message": "Select at least one number."}
    selected = [int(k) for k, v in checked.items() if v and not k.startswith("__")]
    if not selected:
        return {"status": "incomplete", "message": "Select at least one number."}
    result = prod(selected)
    return {
        "status": "computed",
        "selected": sorted(selected),
        "count": len(selected),
        "product": result,
        "message": f"{' x '.join(str(n) for n in sorted(selected))} = {result}",
    }


# --- Experiment 2: Cross-field validation ---

CITY_OPTIONS = {
    "USA": ["New York", "Los Angeles", "Chicago", "Houston"],
    "UK": ["London", "Manchester", "Birmingham", "Edinburgh"],
    "Japan": ["Tokyo", "Osaka", "Kyoto", "Sapporo"],
    "Germany": ["Berlin", "Munich", "Hamburg", "Frankfurt"],
}


# --- Experiment 3: Action with side effects ---

def reset_selections(context: dict, store: Store, scope: str):
    """Reset the country and city selections."""
    store.set(scope, "country", None)
    store.set(scope, "city", None)
    return {"message": "Country and city selections cleared."}


definition = PageForm(
    key="weird-experiments",
    label="Weird Experiments",
    instruction="A playground exercising all four new eigenform capabilities.",
    eigenforms=[
        # === Experiment 1: Number Multiplier ===
        CheckboxForm(key="numbers", label="1. Number Multiplier",
                     instruction="Select numbers to multiply together.",
                     items=[str(n) for n in range(1, 21)]),
        ComputedForm(key="product", label="Product",
                     instruction="The product of all selected numbers.",
                     depends_on=["numbers"],
                     compute_fn=multiply_selected,
                     store_result=True),

        # === Experiment 2: Cross-Field Validation ===
        NumberForm(key="start_val", label="2a. Start Value",
                   instruction="Enter a starting number.",
                   min_val=0, max_val=100),
        NumberForm(key="end_val", label="2b. End Value",
                   instruction="Enter an ending number (must be greater than start).",
                   min_val=0, max_val=100),
        DateForm(key="start_date", label="2c. Start Date",
                 instruction="Pick a start date."),
        DateForm(key="end_date", label="2d. End Date",
                 instruction="Pick an end date (must be after start date)."),
        ValidationForm(key="validation", label="2. Validation Rules",
                       instruction="Cross-field constraints evaluated live.",
                       rules=[
                           ValidationRule(
                               name="end > start",
                               depends_on=["start_val", "end_val"],
                               check_fn=lambda v: v["end_val"] > v["start_val"],
                               message="End value must be greater than start value.",
                           ),
                           ValidationRule(
                               name="end date after start date",
                               depends_on=["start_date", "end_date"],
                               check_fn=lambda v: v["end_date"] > v["start_date"],
                               message="End date must be after start date.",
                           ),
                       ]),

        # === Experiment 3: Dynamic Choice + Action ===
        ChoiceForm(key="country", label="3a. Country",
                   instruction="Select a country.",
                   options=list(CITY_OPTIONS.keys())),
        DynamicChoiceForm(key="city", label="3b. City",
                          instruction="Select a city (options depend on country).",
                          depends_on="country",
                          static_options=CITY_OPTIONS),
        ActionForm(key="reset_geo", label="3c. Reset Selections",
                   instruction="Clear country and city selections.",
                   action_label="Reset",
                   action_fn=reset_selections,
                   depends_on=["country", "city"],
                   writes_to=["country", "city"],
                   precondition_fn=lambda ctx: ctx.get("country") is not None or ctx.get("city") is not None,
                   precondition_message="Nothing to reset.",
                   confirm=True),

        # === Experiment 4: Repeater ===
        RepeaterForm(key="team", label="4. Team Members",
                     instruction="Add team members. Each has a name, role, and skill level.",
                     entry_label="Member",
                     min_entries=1,
                     max_entries=5,
                     template=[
                         TextForm(key="name", label="Name", instruction="Full name."),
                         ChoiceForm(key="role", label="Role", instruction="Select a role.",
                                    options=["Developer", "QA", "PM", "Designer"]),
                         NumberForm(key="experience", label="Years of Experience",
                                    instruction="How many years?",
                                    min_val=0, max_val=50, integer=True),
                     ]),
    ],
)
