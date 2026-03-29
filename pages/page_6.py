"""Page 6 — Change request form (MultiForm + ChoiceForm + CheckboxForm + ListForm)."""

from engine.choiceform import ChoiceForm
from engine.checkboxform import CheckboxForm
from engine.listform import ListForm
from engine.multiform import FieldDescriptor, MultiForm
from engine.pageform import PageForm


definition = PageForm(key="page-6", label="Page 6", instruction="A change request form showcasing ChoiceForm, ListForm, and MultiForm.", eigenforms=[
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
])
