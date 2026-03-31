"""
Page Builder — a mutable page for composing eigenform structures.

Starts with a name and description, then exposes the full mutable_structure
affordance set: add any eigenform type from the registry, remove, reorder.
Build the structure first, then refine each eigenform's content.
"""

from engine.textform import TextForm
from engine.memoform import MemoForm
from engine.pageform import PageForm

definition = PageForm(
    key="page-builder",
    label="Page Builder",
    instruction=(
        "Build a page by adding eigenforms from the registry. "
        "Start with the structure — add, remove, and reorder elements — "
        "then refine each one's content."
    ),
    mutable_structure=True,
    eigenforms=[
        TextForm(
            key="page-name",
            label="Page Name",
            instruction="A name for the page you are building.",
        ),
        MemoForm(
            key="page-description",
            label="Description",
            instruction="Describe the purpose of this page.",
        ),
    ],
)
