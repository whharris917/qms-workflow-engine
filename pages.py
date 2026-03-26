"""Page definitions — the application's content layer.

Each function returns a bound PageForm ready to serve. Definitions are
templates; bind() produces live instances with their own Store.
"""

from pathlib import Path

from engine.chain import ChainForm
from engine.choice import ChoiceForm
from engine.eigenforms import CheckboxForm, TextForm
from engine.listform import ListForm
from engine.multi import FieldDescriptor, MultiForm
from engine.page import PageForm
from engine.rubiks import RubiksCubeForm
from engine.tab import TabForm
from engine.table import TableForm


def build_pages(data_dir: Path) -> dict[str, PageForm]:
    """Build and bind all demo pages. Returns {page_id: bound PageForm}."""

    title_def = TextForm(key="title", label="Document Title", instruction="A short, descriptive title.")
    purpose_def = TextForm(key="purpose", label="Purpose", instruction="What problem does this CR solve?")
    impacts_def = CheckboxForm(
        key="impacts", label="Impact Areas", instruction="Select all that apply.",
        items=["code", "documentation", "tests", "infrastructure"],
    )

    return {
        "1": PageForm(key="1", label="Page 1", eigenforms=[title_def, purpose_def, impacts_def])
                .bind(data_dir=data_dir, scope="1", url_prefix="/page/1"),
        "2": PageForm(key="2", label="Page 2", instruction="Fill out each tab to complete the change request.", eigenforms=[
                    TabForm(key="tabs", label="Details", tabs={
                        "basic": TextForm(key="title", label="Document Title", instruction="A short, descriptive title."),
                        "scope": TextForm(key="scope", label="Scope", instruction="What is affected by this change?"),
                        "impact": CheckboxForm(key="impacts", label="Impact Areas", instruction="Select all that apply.",
                                               items=["code", "documentation", "tests", "infrastructure"]),
                    }),
                ]).bind(data_dir=data_dir, scope="2", url_prefix="/page/2"),
        "3": PageForm(key="3", label="Page 3", eigenforms=[
                    RubiksCubeForm(key="cube", label="Rubik's Cube",
                                   instruction="A fully functional cube. Rotate any face."),
                ]).bind(data_dir=data_dir, scope="3", url_prefix="/page/3"),
        "4": PageForm(key="4", label="Page 4", instruction="Complete each step in sequence.", eigenforms=[
                    ChainForm(key="chain", label="Change Request Wizard", instruction="Fill out each step to proceed.", steps=[
                        TextForm(key="title", label="Document Title", instruction="A short, descriptive title."),
                        TextForm(key="purpose", label="Purpose", instruction="What problem does this CR solve?"),
                        TextForm(key="scope", label="Scope", instruction="What is affected by this change?"),
                        CheckboxForm(key="impacts", label="Impact Areas", instruction="Select all that apply.",
                                     items=["code", "documentation", "tests", "infrastructure"]),
                    ]),
                ]).bind(data_dir=data_dir, scope="4", url_prefix="/page/4"),
        "5": PageForm(key="5", label="Page 5", instruction="Build and populate a table.", eigenforms=[
                    TableForm(key="table", label="Data Table",
                              instruction="Add columns, then rows, then fill in cells."),
                ]).bind(data_dir=data_dir, scope="5", url_prefix="/page/5"),
        "6": PageForm(key="6", label="Page 6", instruction="A change request form showcasing ChoiceForm, ListForm, and MultiForm.", eigenforms=[
                    MultiForm(key="basic_info", label="Basic Information",
                              instruction="Provide the core details for this change request.",
                              fields=[
                                  FieldDescriptor(key="title", label="Title", instruction="Short descriptive title."),
                                  FieldDescriptor(key="author", label="Author", instruction="Who is proposing this change?"),
                                  FieldDescriptor(key="priority", label="Priority", type="choice",
                                                  options=["Low", "Medium", "High", "Critical"]),
                              ]),
                    ChoiceForm(key="change_type", label="Change Type",
                               instruction="What kind of change is this?",
                               options=["New Feature", "Bug Fix", "Refactor", "Documentation", "Infrastructure"]),
                    CheckboxForm(key="affected_areas", label="Affected Areas",
                                 instruction="Select all areas impacted by this change.",
                                 items=["frontend", "backend", "database", "API", "CI/CD"]),
                    ListForm(key="requirements", label="Requirements",
                             instruction="List the requirements for this change."),
                    ListForm(key="risks", label="Risks",
                             instruction="List any risks or concerns."),
                ]).bind(data_dir=data_dir, scope="6", url_prefix="/page/6"),
    }
