"""Control Flow Gallery."""

from engine.pagecomponent import PageComponent
from engine.historycomponent import HistoryComponent
from engine.navigationcomponent import NavigationComponent
from engine.textcomponent import TextComponent
from engine.checkboxcomponent import CheckboxComponent
from engine.choicecomponent import ChoiceComponent
from engine.booleancomponent import BooleanComponent
from engine.switchcomponent import SwitchComponent
from engine.numbercomponent import NumberComponent

SequenceDemo = NavigationComponent(
    key="sequence-demo",
    label="NavigationComponent — Gated Sequential Workflow",
    instruction=(
        "A gated sequence of steps. Each step must be completed "
        "before the next unlocks. You can revisit completed steps, "
        "but you cannot skip ahead."
    ),
    steps=[
        TextComponent(
            key="project-name",
            label="Step 1: Project Name",
            instruction="Enter a name for your project.",
        ),
        ChoiceComponent(
            key="project-type",
            label="Step 2: Project Type",
            instruction="Select the type of project.",
            options=["Web Application", "CLI Tool", "Library", "Mobile App"],
        ),
        CheckboxComponent(
            key="features",
            label="Step 3: Features",
            instruction="Select which features to include.",
            items=["Authentication", "Database", "API", "Logging", "Tests"],
        ),
    ],
)

TechnicalReview = NavigationComponent(
    key="technical-review",
    label="Technical Review",
    instruction="Complete the technical review.",
    steps=[
        ChoiceComponent(
            key="feasibility",
            label="Feasibility",
            instruction="Is the proposal technically feasible?",
            options=["Feasible", "Feasible with changes", "Not feasible"],
        ),
        TextComponent(multiline=True,
            key="tech-notes",
            label="Technical Notes",
            instruction="Provide technical review notes.",
        ),
    ],
)

BusinessReview = NavigationComponent(
    key="business-review",
    label="Business Review",
    instruction="Complete the business review.",
    steps=[
        ChoiceComponent(
            key="priority",
            label="Priority",
            instruction="What priority should this receive?",
            options=["Critical", "High", "Medium", "Low"],
        ),
        TextComponent(multiline=True,
            key="biz-notes",
            label="Business Notes",
            instruction="Provide business review notes.",
        ),
    ],
)

ParallelReviews = NavigationComponent(
    key="parallel-reviews",
    label="2. Parallel Reviews",
    mode="tabs",
    instruction="Both branches must be completed. Switch freely between them.",
    steps=[TechnicalReview, BusinessReview],
)

ForkMergeDemo = NavigationComponent(
    key="fork-merge-demo",
    label="Fork / Merge — Parallel Branches",
    instruction=(
        "Demonstrates a fork/merge pattern. Step 1 is the entry point. "
        "Step 2 forks into two parallel branches (tabs) — you can switch "
        "freely between them, but both must be completed before step 3 "
        "(the merge point) unlocks."
    ),
    steps=[
        TextComponent(
            key="proposal",
            label="1. Proposal",
            instruction="Describe your proposal. This is the fork point — once complete, two independent review branches open.",
        ),
        ParallelReviews,
        BooleanComponent(
            key="approved",
            label="3. Final Decision",
            instruction="Both reviews are complete. Approve or reject the proposal.",
            true_label="Approve",
            false_label="Reject",
        ),
    ],
)

BugBranch = NavigationComponent(
    key="bug-branch",
    label="Bug Report Branch",
    instruction="Describe the bug.",
    steps=[
        TextComponent(multiline=True,
            key="repro-steps",
            label="Reproduction Steps",
            instruction="How do you reproduce the bug?",
        ),
        ChoiceComponent(
            key="severity",
            label="Severity",
            instruction="How severe is this bug?",
            options=["Critical", "Major", "Minor", "Cosmetic"],
        ),
    ],
)

FeatureBranch = NavigationComponent(
    key="feature-branch",
    label="Feature Request Branch",
    instruction="Describe the feature.",
    steps=[
        TextComponent(multiline=True,
            key="user-story",
            label="User Story",
            instruction="As a [role], I want [goal], so that [benefit].",
        ),
        NumberComponent(
            key="effort-estimate",
            label="Effort Estimate (days)",
            instruction="Estimate the effort in days.",
            min_val=1,
            max_val=90,
            step=1,
        ),
    ],
)

IssueBranch = SwitchComponent(
    key="issue-branch",
    label="2. Details",
    instruction="Complete the branch for your selected issue type.",
    depends_on="issue-type",
    cases={
        "Bug Report": BugBranch,
        "Feature Request": FeatureBranch,
        "Refactor": TextComponent(multiline=True,
            key="refactor-scope",
            label="Refactor Scope",
            instruction="Describe what will be refactored and why.",
        ),
    },
)

RoutingDemo = NavigationComponent(
    key="routing-demo",
    label="Routing — Conditional Branches",
    instruction=(
        "Demonstrates mutually-exclusive routing. The choice in step 1 "
        "determines which branch appears in step 2. Changing the route "
        "switches to a different branch — each branch preserves its own "
        "state independently. Step 3 unlocks once the active branch is complete."
    ),
    steps=[
        ChoiceComponent(
            key="issue-type",
            label="1. Issue Type",
            instruction="Select the type of issue. This determines the workflow branch.",
            options=["Bug Report", "Feature Request", "Refactor"],
        ),
        IssueBranch,
        BooleanComponent(
            key="confirmed",
            label="3. Submit",
            instruction="The selected branch is complete. Confirm submission.",
            true_label="Submit",
            false_label="Cancel",
        ),
    ],
)

HistoryDemo = HistoryComponent(
    key="history-demo",
    label="HistoryComponent",
    instruction=(
        "Wraps a component with append-only change history. "
        "Every change is recorded with a timestamp. "
        "Browse previous versions read-only — the history can never be edited."
    ),
    component=TextComponent(
        key="tracked-text",
        label="Tracked Text",
        instruction="Edit this value. Each change is recorded in the history.",
    ),
)

definition = PageComponent(
    key="control-flow-gallery",
    label="Control Flow Gallery",
    components=[
        SequenceDemo,
        ForkMergeDemo,
        RoutingDemo,
        HistoryDemo,
    ],
)