"""Page 1 — Basic eigenforms: TextForm + TextForm + CheckboxForm."""

from engine.eigenforms import CheckboxForm, TextForm
from engine.page import PageForm


definition = PageForm(key="page-1", label="Page 1", eigenforms=[
    TextForm(key="title", label="Document Title", instruction="A short, descriptive title."),
    TextForm(key="purpose", label="Purpose", instruction="What problem does this CR solve?"),
    CheckboxForm(
        key="impacts", label="Impact Areas", instruction="Select all that apply.",
        items=["code", "documentation", "tests", "infrastructure"],
    ),
])
