"""HTMX Lab — test page for HTMX-native eigenforms."""

from engine.textform import TextForm
from engine.listformx import ListFormX
from engine.tableformx import TableFormX
from engine.choiceformx import ChoiceFormX
from engine.checkboxformx import CheckboxFormX
from engine.numberformx import NumberFormX
from engine.booleanformx import BooleanFormX
from engine.memoformx import MemoFormX
from engine.pageform import PageForm


definition = PageForm(
    key="htmx-lab",
    label="HTMX Lab",
    eigenforms=[
        TextForm(
            key="title",
            label="Project Title",
            instruction="Enter a project title.",
        ),
        ListFormX(
            key="simple-list",
            label="Simple List",
            instruction="A basic list with no constraints.",
        ),
        ListFormX(
            key="constrained-list",
            label="Constrained List",
            instruction="A list with fixed items and ordering constraints.",
            fixed_items=["Design", "Build", "Test", "Deploy"],
            must_follow={"item_2": ["item_1"], "item_3": ["item_2"]},
            editable=True,
        ),
        ChoiceFormX(
            key="priority",
            label="Priority",
            instruction="Select a priority level.",
            options=["Low", "Medium", "High", "Critical"],
        ),
        CheckboxFormX(
            key="tags",
            label="Tags",
            instruction="Select applicable tags.",
            items=["Frontend", "Backend", "Database", "DevOps", "Security"],
        ),
        NumberFormX(
            key="score",
            label="Score",
            instruction="Enter a score from 0 to 100.",
            min_val=0,
            max_val=100,
            step=5,
        ),
        BooleanFormX(
            key="approved",
            label="Approved",
            instruction="Has this been approved?",
            true_label="Approved",
            false_label="Rejected",
        ),
        MemoFormX(
            key="notes",
            label="Notes",
            instruction="Enter any additional notes.",
            placeholder="Type your notes here...",
            min_length=10,
        ),
        TableFormX(
            key="simple-table",
            label="Simple Table",
            instruction="A basic table with dynamic columns and rows.",
            fixed_columns=["Name", "Role"],
        ),
        TableFormX(
            key="constrained-table",
            label="Constrained Table",
            instruction="A table with row constraints and auto-chain support.",
            fixed_columns=["Stage", "Owner", "Status"],
            fixed_rows=[
                {"col_0": "Design", "col_1": "", "col_2": ""},
                {"col_0": "Build", "col_1": "", "col_2": ""},
                {"col_0": "Test", "col_1": "", "col_2": ""},
                {"col_0": "Deploy", "col_1": "", "col_2": ""},
            ],
            row_must_follow={"row_1": ["row_0"], "row_2": ["row_1"], "row_3": ["row_2"]},
            allow_row_constraints=True,
        ),
    ],
)
