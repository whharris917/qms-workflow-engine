"""Page 2 — NavigationForm (tabs mode) with three tabs."""

from engine.checkboxform import CheckboxForm
from engine.textform import TextForm
from engine.pageform import PageForm
from engine.navigationform import NavigationForm


definition = PageForm(key="page-2", label="Page 2", instruction="Fill out each tab to complete the change request.", eigenforms=[
    NavigationForm(key="tabs", label="Details", mode="tabs", steps=[
        TextForm(key="title", label="Document Title", instruction="A short, descriptive title."),
        TextForm(key="scope", label="Scope", instruction="What is affected by this change?"),
        CheckboxForm(key="impacts", label="Impact Areas", instruction="Select all that apply.",
                     items=["code", "documentation", "tests", "infrastructure"]),
    ]),
])
