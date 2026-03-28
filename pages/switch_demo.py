"""Switch Demo — exercises SwitchForm with different composition shapes.

Demonstrates:
- Basic SwitchForm: choice drives which form subtree is active
- Nested containers inside cases (GroupForm, ChainForm)
- State preservation across case switches
"""

from engine.chain import ChainForm
from engine.choice import ChoiceForm
from engine.eigenforms import CheckboxForm, TextForm
from engine.group import GroupForm
from engine.number import NumberForm
from engine.page import PageForm
from engine.switch import SwitchForm


# --- Parameterized compositions for the cases ---

class BugReport(GroupForm):
    """Bug report form: steps to reproduce, severity, affected area."""
    def __init__(self, key, **kwargs):
        super().__init__(key=key, label="Bug Report", eigenforms=[
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


class FeatureRequest(GroupForm):
    """Feature request form: description, justification, priority."""
    def __init__(self, key, **kwargs):
        super().__init__(key=key, label="Feature Request", eigenforms=[
            TextForm(key="description", label="Description",
                     instruction="What feature do you want?"),
            TextForm(key="justification", label="Justification",
                     instruction="Why is this needed?"),
            ChoiceForm(key="priority", label="Priority",
                       instruction="How important is this?",
                       options=["Must Have", "Should Have", "Nice to Have"]),
            NumberForm(key="effort", label="Estimated Effort (days)",
                       instruction="Rough estimate in person-days.",
                       min_val=1, max_val=365, integer=True),
        ], **kwargs)


class Question(GroupForm):
    """General question form: question text and context."""
    def __init__(self, key, **kwargs):
        super().__init__(key=key, label="Question", eigenforms=[
            TextForm(key="question", label="Your Question",
                     instruction="What do you want to know?"),
            TextForm(key="context", label="Context",
                     instruction="Any background that helps answer your question."),
        ], **kwargs)


definition = PageForm(
    key="switch-demo",
    label="Switch Demo",
    instruction="Select a ticket type to see the appropriate form.",
    eigenforms=[
        ChoiceForm(key="ticket_type", label="Ticket Type",
                   instruction="What kind of ticket is this?",
                   options=["bug", "feature", "question"]),
        SwitchForm(key="ticket_form", label="Ticket Details",
                   instruction="Fill out the details for your ticket.",
                   depends_on="ticket_type",
                   cases={
                       "bug": BugReport("details"),
                       "feature": FeatureRequest("details"),
                       "question": Question("details"),
                   }),
    ],
)
