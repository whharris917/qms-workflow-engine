"""Reactive binding demo — NumberForm bounds derived from a sibling's value.

Tier selection drives the allowed range on a usage slider. When Tier changes,
the slider's min/max resolve to new bounds on the next render — no separate
DynamicNumberForm class is needed.

This page is the validation surface for `SiblingBind` (engine/sibling_bind.py).
"""

from engine.page import Page
from engine.choiceform import ChoiceForm
from engine.numberform import NumberForm
from engine.infodisplay import InfoDisplay
from engine.sibling_bind import SiblingBind


TIER_LIMITS = {
    "Free": (0, 100),
    "Pro": (0, 1000),
    "Enterprise": (0, 100000),
}


definition = Page(
    key="reactive-demo",
    label="Reactive Binding Demo",
    instruction=(
        "Pick a tier. The monthly-usage field's max changes based on the tier. "
        "A value entered under one tier that exceeds the new tier's cap is "
        "flagged stale rather than silently accepted."
    ),
    components=[
        ChoiceForm(
            key="tier",
            label="Subscription tier",
            instruction="Select a plan.",
            options=list(TIER_LIMITS.keys()),
        ),
        NumberForm(
            key="usage",
            label="Monthly usage",
            instruction="Enter a usage count within the tier's allowance.",
            min_val=SiblingBind("tier", lambda t: TIER_LIMITS[t][0]),
            max_val=SiblingBind("tier", lambda t: TIER_LIMITS[t][1]),
        ),
        InfoDisplay(
            key="notes",
            label="What to try",
            text=(
                "1. Pick Free tier, enter 50 — accepted.\n"
                "2. Pick Enterprise, enter 50000 — accepted.\n"
                "3. Switch back to Free — the stored 50000 is now flagged stale.\n"
                "4. Try to set 50000 while on Free — rejected: above maximum 100."
            ),
        ),
    ],
)
