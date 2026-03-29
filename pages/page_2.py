"""Page 2 — TabForm with three tabs."""

from engine.checkboxform import CheckboxForm
from engine.textform import TextForm
from engine.pageform import PageForm
from engine.tabform import TabForm


definition = PageForm(key="page-2", label="Page 2", instruction="Fill out each tab to complete the change request.", eigenforms=[
    TabForm(key="tabs", label="Details", tabs={
        "basic": TextForm(key="title", label="Document Title", instruction="A short, descriptive title."),
        "scope": TextForm(key="scope", label="Scope", instruction="What is affected by this change?"),
        "impact": CheckboxForm(key="impacts", label="Impact Areas", instruction="Select all that apply.",
                               items=["code", "documentation", "tests", "infrastructure"]),
    }),
])
