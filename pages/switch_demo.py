"""Switch Demo — exercises SwitchComponent with different composition shapes.

Demonstrates:
- Basic SwitchComponent: choice drives which form subtree is active
- Nested containers inside cases (GroupComponent, ChainForm)
- State preservation across case switches
"""

from engine.choicecomponent import ChoiceComponent
from engine.checkboxcomponent import CheckboxComponent
from engine.textcomponent import TextComponent
from engine.groupcomponent import GroupComponent
from engine.numbercomponent import NumberComponent
from engine.pagecomponent import PageComponent
from engine.switchcomponent import SwitchComponent


# --- Parameterized compositions for the cases ---

class BugReport(GroupComponent):
    """Bug report form: steps to reproduce, severity, affected area."""
    def __init__(self, key, **kwargs):
        super().__init__(key=key, label="Bug Report", components=[
            TextComponent(key="summary", label="Summary",
                     instruction="One-line description of the bug."),
            TextComponent(key="steps", label="Steps to Reproduce",
                     instruction="How to trigger the bug."),
            ChoiceComponent(key="severity", label="Severity",
                       instruction="How severe is this?",
                       options=["Critical", "Major", "Minor", "Cosmetic"]),
            CheckboxComponent(key="areas", label="Affected Areas",
                         instruction="Select all affected areas.",
                         items=["UI", "Backend", "Database", "API", "Auth"]),
        ], **kwargs)


class FeatureRequest(GroupComponent):
    """Feature request form: description, justification, priority."""
    def __init__(self, key, **kwargs):
        super().__init__(key=key, label="Feature Request", components=[
            TextComponent(key="description", label="Description",
                     instruction="What feature do you want?"),
            TextComponent(key="justification", label="Justification",
                     instruction="Why is this needed?"),
            ChoiceComponent(key="priority", label="Priority",
                       instruction="How important is this?",
                       options=["Must Have", "Should Have", "Nice to Have"]),
            NumberComponent(key="effort", label="Estimated Effort (days)",
                       instruction="Rough estimate in person-days.",
                       min_val=1, max_val=365, step=1),
        ], **kwargs)


class Question(GroupComponent):
    """General question form: question text and context."""
    def __init__(self, key, **kwargs):
        super().__init__(key=key, label="Question", components=[
            TextComponent(key="question", label="Your Question",
                     instruction="What do you want to know?"),
            TextComponent(key="context", label="Context",
                     instruction="Any background that helps answer your question."),
        ], **kwargs)


definition = PageComponent(
    key="switch-demo",
    label="Switch Demo",
    instruction="Select a ticket type to see the appropriate form.",
    components=[
        ChoiceComponent(key="ticket_type", label="Ticket Type",
                   instruction="What kind of ticket is this?",
                   options=["bug", "feature", "question"]),
        SwitchComponent(key="ticket_form", label="Ticket Details",
                   instruction="Fill out the details for your ticket.",
                   depends_on="ticket_type",
                   cases={
                       "bug": BugReport("details"),
                       "feature": FeatureRequest("details"),
                       "question": Question("details"),
                   }),
    ],
)
