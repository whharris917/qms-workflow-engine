"""
Page Builder — a mutable page for composing eigenform structures.

Embeds the Eigenform Reference Menu for type documentation, then
provides a mutable workspace below it. Add eigenforms from the
registry, remove, reorder, then refine each one's content.
"""

from engine.pageform import PageForm
from pages.eigenform_reference import definition as _reference_seed

definition = PageForm(
    key="page-builder",
    label="Page Builder",
    instruction=(
        "Build a page by adding eigenforms from the registry. "
        "The Eigenform Reference Menu below documents all available types. "
        "Add eigenforms, then use edit mode to configure them."
    ),
    mutable_structure=True,
    eigenforms=[_reference_seed],
)
