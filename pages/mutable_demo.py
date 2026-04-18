"""Mutable Demo — a page whose structure can be modified at runtime.

Starts with a single TextForm. The agent or user can add, remove,
and reorder components using structural actions. This is Phase D
of the fractal complexity plan.
"""

from engine.textform import TextForm
from engine.page import Page


definition = Page(
    key="mutable-demo",
    label="Mutable Demo",
    instruction="This page's structure can be modified. Add, remove, and reorder components.",
    mutable_structure=True,
    components=[
        TextForm(key="welcome", label="Welcome Message",
                 instruction="Type anything to get started."),
    ],
)
