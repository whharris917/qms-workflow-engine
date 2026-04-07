"""Nested Tabs Test — exercises vertical (page>nav) vs horizontal (nested) layout."""

from engine.textform import TextForm
from engine.groupform import GroupForm
from engine.pageform import PageForm
from engine.navigationform import NavigationForm
from engine.checkboxform import CheckboxForm
from engine.booleanform import BooleanForm


definition = PageForm(
    key="nested-tabs-test",
    label="Nested Tabs Test",
    instruction="Top-level NavigationForm gets vertical sidebar. Nested NavigationForms get horizontal tabs.",
    eigenforms=[
        NavigationForm(key="outer", label="Outer Nav", instruction="This should be a vertical sidebar.", mode="tabs", steps=[
            GroupForm(key="basics", label="Basic Fields", instruction="A GroupForm with simple fields.", eigenforms=[
                TextForm(key="name", label="Name", instruction="Enter your name."),
                TextForm(key="email", label="Email", instruction="Enter your email."),
            ]),
            NavigationForm(key="nested-tabs", label="Nested Tabs", instruction="This should be horizontal tabs.", mode="tabs", steps=[
                TextForm(key="tab-a", label="Tab A", instruction="First nested tab."),
                TextForm(key="tab-b", label="Tab B", instruction="Second nested tab."),
                TextForm(key="tab-c", label="Tab C", instruction="Third nested tab."),
            ]),
            NavigationForm(key="nested-chain", label="Nested Chain", instruction="This should be horizontal steps.", mode="chain", steps=[
                TextForm(key="step-1", label="Step 1", instruction="First step."),
                BooleanForm(key="step-2", label="Step 2", instruction="Confirm something."),
                TextForm(key="step-3", label="Step 3", instruction="Final step."),
            ]),
            NavigationForm(key="nested-sequence", label="Nested Sequence", instruction="Horizontal sequence nav.", mode="sequence", steps=[
                CheckboxForm(key="checklist-a", label="Checklist A", instruction="Pick items.", items=["Alpha", "Beta", "Gamma"]),
                CheckboxForm(key="checklist-b", label="Checklist B", instruction="Pick more.", items=["Delta", "Epsilon"]),
            ]),
        ]),
    ],
)
