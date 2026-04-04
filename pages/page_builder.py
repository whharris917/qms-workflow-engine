"""
Page Builder — a mutable page for composing eigenform structures.

Starts empty. Add eigenforms from the registry, remove, reorder.
Build the structure first, then refine each one's content.
"""

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
    eigenforms=[],
)
