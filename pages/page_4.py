"""Page 4 — ChainForm wizard (4-step sequential form)."""

from engine.chainform import ChainForm
from engine.checkboxform import CheckboxForm
from engine.textform import TextForm
from engine.pageform import PageForm


definition = PageForm(key="page-4", label="Page 4", instruction="Complete each step in sequence.", eigenforms=[
    ChainForm(key="chain", label="Change Request Wizard", instruction="Fill out each step to proceed.", steps=[
        TextForm(key="title", label="Document Title", instruction="A short, descriptive title."),
        TextForm(key="purpose", label="Purpose", instruction="What problem does this CR solve?"),
        TextForm(key="scope", label="Scope", instruction="What is affected by this change?"),
        CheckboxForm(key="impacts", label="Impact Areas", instruction="Select all that apply.",
                     items=["code", "documentation", "tests", "infrastructure"]),
    ]),
])
