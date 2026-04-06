"""Nested Tabs Test — simple case for testing wrapper rendering."""

from engine.textform import TextForm
from engine.groupform import GroupForm
from engine.pageform import PageForm
from engine.navigationform import NavigationForm


definition = PageForm(
    key="nested-tabs-test",
    label="Nested Tabs Test",
    instruction="Simple NavigationForm with a TextForm tab and a GroupForm tab.",
    eigenforms=[
        NavigationForm(key="nav", label="Nav", instruction="Top-level nav.", mode="tabs", editable=True, steps=[
            TextForm(key="solo", label="Solo Field", instruction="A standalone TextForm in the first tab.", editable=True),
            GroupForm(key="pair", label="Paired Fields", instruction="A GroupForm containing two TextForms.", editable=True, eigenforms=[
                TextForm(key="first", label="First", instruction="First field in the group.", editable=True),
                TextForm(key="second", label="Second", instruction="Second field in the group.", editable=True),
            ]),
        ]),
    ],
)
