"""Example Table — TableForm (dynamic columns and rows)."""

from engine.page import PageForm
from engine.table import TableForm


definition = PageForm(key="example-table", label="Example Table", instruction="Build and populate a table.", eigenforms=[
    TableForm(key="table", label="Data Table",
              instruction="Add columns, then rows, then fill in cells."),
])
