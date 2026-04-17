"""Mutable Demo — a page whose structure can be modified at runtime.

Starts with a single TextComponent. The agent or user can add, remove,
and reorder components using structural actions. This is Phase D
of the fractal complexity plan.
"""

from engine.textcomponent import TextComponent
from engine.pagecomponent import PageComponent


definition = PageComponent(
    key="mutable-demo",
    label="Mutable Demo",
    instruction="This page's structure can be modified. Add, remove, and reorder components.",
    mutable_structure=True,
    components=[
        TextComponent(key="welcome", label="Welcome Message",
                 instruction="Type anything to get started."),
    ],
)
