"""Control Flow Gallery."""

from engine.pageform import PageForm
from engine.historyform import HistoryForm
from engine.textform import TextForm

definition = PageForm(
    key="control-flow-gallery",
    label="Control Flow Gallery",
    eigenforms=[
        HistoryForm(
            key="history-demo",
            label="HistoryForm",
            instruction=(
                "Wraps an eigenform with append-only change history. "
                "Every change is recorded with a timestamp. "
                "Browse previous versions read-only — the history can never be edited."
            ),
            eigenform=TextForm(
                key="tracked-text",
                label="Tracked Text",
                instruction="Edit this value. Each change is recorded in the history.",
            ),
        ),
    ],
)
