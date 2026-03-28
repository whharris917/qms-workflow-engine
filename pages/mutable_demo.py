"""Mutable Demo — a page whose structure can be modified at runtime.

Starts with a single TextForm. The agent or user can add, remove,
and reorder eigenforms using structural actions. This is Phase D
of the fractal complexity plan.
"""

from engine.eigenforms import TextForm
from engine.page import PageForm


definition = PageForm(
    key="mutable-demo",
    label="Mutable Demo",
    instruction="This page's structure can be modified. Add, remove, and reorder eigenforms.",
    mutable_structure=True,
    eigenforms=[
        TextForm(key="welcome", label="Welcome Message",
                 instruction="Type anything to get started."),
    ],
)
