"""Example Table — TableForm (dynamic columns and rows)."""

from engine.page import Page
from engine.tableform import TableForm


definition = Page(key="example-table", label="Example Table", instruction="Build and populate a table.", components=[
    TableForm(key="table", label="Data Table",
              instruction="Add columns, then rows, then fill in cells."),
])
