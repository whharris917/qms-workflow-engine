"""Control Flow Gallery."""

from engine.page import Page
from engine.historizer import Historizer
from engine.navigation import Navigation
from engine.textform import TextForm
from engine.checkboxform import CheckboxForm
from engine.choiceform import ChoiceForm
from engine.booleanform import BooleanForm
from engine.switch import Switch
from engine.numberform import NumberForm

SequenceDemo = Navigation(
    key="sequence-demo",
    label="Navigation — Gated Sequential Workflow",
    instruction=(
        "A gated sequence of steps. Each step must be completed "
        "before the next unlocks. You can revisit completed steps, "
        "but you cannot skip ahead."
    ),
    steps=[
        TextForm(
            key="project-name",
            label="Step 1: Project Name",
            instruction="Enter a name for your project.",
        ),
        ChoiceForm(
            key="project-type",
            label="Step 2: Project Type",
            instruction="Select the type of project.",
            options=["Web Application", "CLI Tool", "Library", "Mobile App"],
        ),
        CheckboxForm(
            key="features",
            label="Step 3: Features",
            instruction="Select which features to include.",
            items=["Authentication", "Database", "API", "Logging", "Tests"],
        ),
    ],
)

TechnicalReview = Navigation(
    key="technical-review",
    label="Technical Review",
    instruction="Complete the technical review.",
    steps=[
        ChoiceForm(
            key="feasibility",
            label="Feasibility",
            instruction="Is the proposal technically feasible?",
            options=["Feasible", "Feasible with changes", "Not feasible"],
        ),
        TextForm(multiline=True,
            key="tech-notes",
            label="Technical Notes",
            instruction="Provide technical review notes.",
        ),
    ],
)

BusinessReview = Navigation(
    key="business-review",
    label="Business Review",
    instruction="Complete the business review.",
    steps=[
        ChoiceForm(
            key="priority",
            label="Priority",
            instruction="What priority should this receive?",
            options=["Critical", "High", "Medium", "Low"],
        ),
        TextForm(multiline=True,
            key="biz-notes",
            label="Business Notes",
            instruction="Provide business review notes.",
        ),
    ],
)

ParallelReviews = Navigation(
    key="parallel-reviews",
    label="2. Parallel Reviews",
    mode="tabs",
    instruction="Both branches must be completed. Switch freely between them.",
    steps=[TechnicalReview, BusinessReview],
)

ForkMergeDemo = Navigation(
    key="fork-merge-demo",
    label="Fork / Merge — Parallel Branches",
    instruction=(
        "Demonstrates a fork/merge pattern. Step 1 is the entry point. "
        "Step 2 forks into two parallel branches (tabs) — you can switch "
        "freely between them, but both must be completed before step 3 "
        "(the merge point) unlocks."
    ),
    steps=[
        TextForm(
            key="proposal",
            label="1. Proposal",
            instruction="Describe your proposal. This is the fork point — once complete, two independent review branches open.",
        ),
        ParallelReviews,
        BooleanForm(
            key="approved",
            label="3. Final Decision",
            instruction="Both reviews are complete. Approve or reject the proposal.",
            true_label="Approve",
            false_label="Reject",
        ),
    ],
)

BugBranch = Navigation(
    key="bug-branch",
    label="Bug Report Branch",
    instruction="Describe the bug.",
    steps=[
        TextForm(multiline=True,
            key="repro-steps",
            label="Reproduction Steps",
            instruction="How do you reproduce the bug?",
        ),
        ChoiceForm(
            key="severity",
            label="Severity",
            instruction="How severe is this bug?",
            options=["Critical", "Major", "Minor", "Cosmetic"],
        ),
    ],
)

FeatureBranch = Navigation(
    key="feature-branch",
    label="Feature Request Branch",
    instruction="Describe the feature.",
    steps=[
        TextForm(multiline=True,
            key="user-story",
            label="User Story",
            instruction="As a [role], I want [goal], so that [benefit].",
        ),
        NumberForm(
            key="effort-estimate",
            label="Effort Estimate (days)",
            instruction="Estimate the effort in days.",
            min_val=1,
            max_val=90,
            step=1,
        ),
    ],
)

IssueBranch = Switch(
    key="issue-branch",
    label="2. Details",
    instruction="Complete the branch for your selected issue type.",
    depends_on="issue-type",
    cases={
        "Bug Report": BugBranch,
        "Feature Request": FeatureBranch,
        "Refactor": TextForm(multiline=True,
            key="refactor-scope",
            label="Refactor Scope",
            instruction="Describe what will be refactored and why.",
        ),
    },
)

RoutingDemo = Navigation(
    key="routing-demo",
    label="Routing — Conditional Branches",
    instruction=(
        "Demonstrates mutually-exclusive routing. The choice in step 1 "
        "determines which branch appears in step 2. Changing the route "
        "switches to a different branch — each branch preserves its own "
        "state independently. Step 3 unlocks once the active branch is complete."
    ),
    steps=[
        ChoiceForm(
            key="issue-type",
            label="1. Issue Type",
            instruction="Select the type of issue. This determines the workflow branch.",
            options=["Bug Report", "Feature Request", "Refactor"],
        ),
        IssueBranch,
        BooleanForm(
            key="confirmed",
            label="3. Submit",
            instruction="The selected branch is complete. Confirm submission.",
            true_label="Submit",
            false_label="Cancel",
        ),
    ],
)

HistoryDemo = Historizer(
    key="history-demo",
    label="Historizer",
    instruction=(
        "Wraps a component with append-only change history. "
        "Every change is recorded with a timestamp. "
        "Browse previous versions read-only — the history can never be edited."
    ),
    component=TextForm(
        key="tracked-text",
        label="Tracked Text",
        instruction="Edit this value. Each change is recorded in the history.",
    ),
)

definition = Page(
    key="control-flow-gallery",
    label="Control Flow Gallery",
    components=[
        SequenceDemo,
        ForkMergeDemo,
        RoutingDemo,
        HistoryDemo,
    ],
)