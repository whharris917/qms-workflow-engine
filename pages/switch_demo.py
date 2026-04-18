"""Switch Demo — exercises Switch with different composition shapes.

Demonstrates:
- Basic Switch: choice drives which form subtree is active
- Nested containers inside cases (Group, ChainForm)
- State preservation across case switches
"""

from engine.choiceform import ChoiceForm
from engine.checkboxform import CheckboxForm
from engine.textform import TextForm
from engine.group import Group
from engine.numberform import NumberForm
from engine.page import Page
from engine.switch import Switch


# --- Parameterized compositions for the cases ---

class BugReport(Group):
    """Bug report form: steps to reproduce, severity, affected area."""
    def __init__(self, key, **kwargs):
        super().__init__(key=key, label="Bug Report", components=[
            TextForm(key="summary", label="Summary",
                     instruction="One-line description of the bug."),
            TextForm(key="steps", label="Steps to Reproduce",
                     instruction="How to trigger the bug."),
            ChoiceForm(key="severity", label="Severity",
                       instruction="How severe is this?",
                       options=["Critical", "Major", "Minor", "Cosmetic"]),
            CheckboxForm(key="areas", label="Affected Areas",
                         instruction="Select all affected areas.",
                         items=["UI", "Backend", "Database", "API", "Auth"]),
        ], **kwargs)


class FeatureRequest(Group):
    """Feature request form: description, justification, priority."""
    def __init__(self, key, **kwargs):
        super().__init__(key=key, label="Feature Request", components=[
            TextForm(key="description", label="Description",
                     instruction="What feature do you want?"),
            TextForm(key="justification", label="Justification",
                     instruction="Why is this needed?"),
            ChoiceForm(key="priority", label="Priority",
                       instruction="How important is this?",
                       options=["Must Have", "Should Have", "Nice to Have"]),
            NumberForm(key="effort", label="Estimated Effort (days)",
                       instruction="Rough estimate in person-days.",
                       min_val=1, max_val=365, step=1),
        ], **kwargs)


class Question(Group):
    """General question form: question text and context."""
    def __init__(self, key, **kwargs):
        super().__init__(key=key, label="Question", components=[
            TextForm(key="question", label="Your Question",
                     instruction="What do you want to know?"),
            TextForm(key="context", label="Context",
                     instruction="Any background that helps answer your question."),
        ], **kwargs)


definition = Page(
    key="switch-demo",
    label="Switch Demo",
    instruction="Select a ticket type to see the appropriate form.",
    components=[
        ChoiceForm(key="ticket_type", label="Ticket Type",
                   instruction="What kind of ticket is this?",
                   options=["bug", "feature", "question"]),
        Switch(key="ticket_form", label="Ticket Details",
                   instruction="Fill out the details for your ticket.",
                   depends_on="ticket_type",
                   cases={
                       "bug": BugReport("details"),
                       "feature": FeatureRequest("details"),
                       "question": Question("details"),
                   }),
    ],
)
