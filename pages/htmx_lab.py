"""HTMX Lab — test page for HTMX-native eigenforms."""

from engine.textform import TextForm
from engine.listformx import ListFormX
from engine.pageform import PageForm


definition = PageForm(
    key="htmx-lab",
    label="HTMX Lab",
    eigenforms=[
        TextForm(
            key="title",
            label="Project Title",
            instruction="Enter a project title.",
        ),
        ListFormX(
            key="simple-list",
            label="Simple List",
            instruction="A basic list with no constraints.",
        ),
        ListFormX(
            key="constrained-list",
            label="Constrained List",
            instruction="A list with fixed items and ordering constraints.",
            fixed_items=["Design", "Build", "Test", "Deploy"],
            must_follow={"item_2": ["item_1"], "item_3": ["item_2"]},
            editable=True,
        ),
    ],
)
