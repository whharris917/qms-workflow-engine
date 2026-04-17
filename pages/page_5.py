"""Example Table — TableComponent (dynamic columns and rows)."""

from engine.pagecomponent import PageComponent
from engine.tablecomponent import TableComponent


definition = PageComponent(key="example-table", label="Example Table", instruction="Build and populate a table.", components=[
    TableComponent(key="table", label="Data Table",
              instruction="Add columns, then rows, then fill in cells."),
])
