"""
Workflow Builder — a tool for designing workflows with stage gates,
parallel paths, conditional branches, merge gates, and acceptance criteria.

Composes 18 eigenform types into a 6-tab builder interface. Showcases
typed columns (ChoiceForm and BooleanForm cells within TableForm).
"""

from engine.textform import TextForm
from engine.memoform import MemoForm
from engine.choiceform import ChoiceForm
from engine.checkboxform import CheckboxForm
from engine.booleanform import BooleanForm
from engine.dateform import DateForm
from engine.ratingform import RatingForm
from engine.listform import ListForm
from engine.tableform import TableForm
from engine.groupform import GroupForm
from engine.tabform import TabForm
from engine.accordionform import AccordionForm
from engine.repeaterform import RepeaterForm
from engine.pageform import PageForm


# ---------------------------------------------------------------------------
# Tab 1: Overview — Workflow Identity & Metadata
# ---------------------------------------------------------------------------

overview = GroupForm(
    key="overview-group",
    label="Workflow Identity",
    instruction=(
        "Define the workflow's identity, scope, and ownership. "
        "This metadata travels with the workflow definition."
    ),
    eigenforms=[
        TextForm(
            key="wf_name",
            label="Workflow Name",
            instruction="A concise, descriptive name for this workflow.",
        ),
        MemoForm(
            key="wf_description",
            label="Description",
            instruction="Describe the purpose, scope, and intended outcome of this workflow.",
            min_length=20,
        ),
        ChoiceForm(
            key="wf_type",
            label="Workflow Type",
            instruction="The structural pattern this workflow follows.",
            options=["Linear", "Parallel", "Conditional", "Hybrid"],
        ),
        TextForm(
            key="wf_owner",
            label="Process Owner",
            instruction="The person or role accountable for this workflow.",
        ),
        DateForm(
            key="wf_target_date",
            label="Target Completion Date",
            instruction="When should this workflow be fully defined and ready for use?",
        ),
    ],
)


# ---------------------------------------------------------------------------
# Tab 2: Stages — The Core Pipeline (typed columns showcase)
# ---------------------------------------------------------------------------

stages = GroupForm(
    key="stages-group",
    label="Stage Pipeline",
    instruction=(
        "Define the stages of your workflow. Each stage has a type that "
        "determines its behavior in the pipeline, and a gate type that "
        "determines what must happen before the next stage begins. "
        "Use the prerequisite constraints to enforce ordering dependencies "
        "between stages, or enable auto-chain to make them strictly sequential."
    ),
    eigenforms=[
        TableForm(
            key="stages",
            label="Stages",
            instruction=(
                "Add stages to the pipeline. Text columns (Stage Name, Owner) "
                "are edited inline. Typed columns (Type, Gate) use their own "
                "controls within each cell. Row ordering constraints define "
                "which stages must precede others."
            ),
            fixed_columns=[
                "Stage Name",
                ChoiceForm(
                    key="_tpl", label="Type",
                    options=[
                        "Sequential",
                        "Parallel Fork",
                        "Conditional Branch",
                        "Merge Point",
                    ],
                ),
                ChoiceForm(
                    key="_tpl", label="Gate",
                    options=[
                        "Approval Gate",
                        "Checklist Gate",
                        "Quality Gate",
                        "Auto-Pass",
                    ],
                ),
                "Owner",
            ],
            allow_row_constraints=True,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Tab 3: Gates — Per-Stage Gate Criteria
# ---------------------------------------------------------------------------

gates = GroupForm(
    key="gates-group",
    label="Gate Definitions",
    instruction=(
        "Define the criteria for each gate in your workflow. Each gate "
        "specifies what evidence is required and whether it blocks "
        "progression to the next stage."
    ),
    eigenforms=[
        RepeaterForm(
            key="gate_defs",
            label="Gate Definitions",
            instruction=(
                "Add one entry per gate. Link each gate to a stage by name, "
                "then specify the gate type, required evidence, and whether "
                "the gate is blocking."
            ),
            entry_label="Gate",
            template=[
                TextForm(
                    key="gate_name",
                    label="Gate Name",
                    instruction="Identify this gate (e.g., 'Design Review Gate', 'Testing Gate').",
                ),
                TextForm(
                    key="gate_stage",
                    label="After Stage",
                    instruction="Which stage does this gate follow? Use the stage name from the Stages tab.",
                ),
                ChoiceForm(
                    key="gate_type",
                    label="Gate Type",
                    instruction="How is this gate evaluated?",
                    options=["Sign-Off", "Checklist", "Threshold", "Peer Review"],
                ),
                CheckboxForm(
                    key="gate_evidence",
                    label="Required Evidence",
                    instruction="Select all evidence types required to pass this gate.",
                    items=[
                        "Documentation",
                        "Test Results",
                        "Approver Signature",
                        "Risk Assessment",
                        "Compliance Check",
                        "Peer Review Record",
                    ],
                ),
                BooleanForm(
                    key="gate_blocking",
                    label="Blocking Gate?",
                    instruction="If blocking, the workflow cannot advance past this gate until it passes.",
                    true_label="Blocking",
                    false_label="Advisory Only",
                ),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Tab 4: Paths — Parallel, Conditional, and Merge
# ---------------------------------------------------------------------------

parallel_paths = TableForm(
    key="parallel_paths",
    label="Parallel Paths",
    instruction=(
        "Define concurrent activities that execute simultaneously. "
        "Specify which stage forks into parallel paths and which stage "
        "they merge back into. Mark whether each path is required "
        "for the merge to succeed."
    ),
    fixed_columns=[
        "Path Name",
        "Fork After Stage",
        "Merge Before Stage",
        BooleanForm(
            key="_tpl", label="Required",
            true_label="Must Complete",
            false_label="Optional",
        ),
    ],
)

conditional_branches = TableForm(
    key="conditional_branches",
    label="Conditional Branches",
    instruction=(
        "Define decision points where the workflow takes different "
        "paths based on a condition. Specify the decision point, "
        "the condition to evaluate, and the target stage for each outcome."
    ),
    fixed_columns=[
        "Decision Point",
        "Condition",
        "If True \u2192 Stage",
        "If False \u2192 Stage",
    ],
)

merge_gates = TableForm(
    key="merge_gates",
    label="Merge Gates",
    instruction=(
        "Define convergence points where parallel or conditional paths "
        "rejoin. The merge strategy determines how many incoming paths "
        "must complete before the workflow proceeds."
    ),
    fixed_columns=[
        "Merge Name",
        ChoiceForm(
            key="_tpl", label="Strategy",
            options=["All Must Complete", "Any Completes", "Quorum"],
        ),
        "Incoming Paths",
    ],
)

paths = AccordionForm(
    key="paths-accordion",
    label="Path Configuration",
    instruction=(
        "Configure the non-linear aspects of your workflow: parallel "
        "execution, conditional branching, and merge points."
    ),
    sections={
        "parallel": parallel_paths,
        "conditional": conditional_branches,
        "merge": merge_gates,
    },
)


# ---------------------------------------------------------------------------
# Tab 5: Acceptance — Final Completion Criteria
# ---------------------------------------------------------------------------

acceptance = GroupForm(
    key="acceptance-group",
    label="Final Acceptance",
    instruction=(
        "Define what must be true for the workflow to be considered "
        "successfully complete. These criteria apply after all stages "
        "and gates have been satisfied."
    ),
    eigenforms=[
        CheckboxForm(
            key="deliverables",
            label="Required Deliverables",
            instruction="Select all deliverables that must be present at workflow completion.",
            items=[
                "Final Report",
                "Test Summary",
                "Risk Register (closed)",
                "Change Log",
                "Compliance Certificate",
                "Training Records",
                "Stakeholder Sign-Off",
            ],
        ),
        ChoiceForm(
            key="approver_role",
            label="Final Approver Role",
            instruction="Who has authority to approve the workflow's completion?",
            options=[
                "Process Owner",
                "Quality Manager",
                "Department Head",
                "Steering Committee",
                "External Auditor",
            ],
        ),
        RatingForm(
            key="min_quality",
            label="Minimum Quality Rating",
            instruction="The minimum quality rating (1-5) required for acceptance.",
            max_rating=5,
            labels={1: "Unacceptable", 2: "Needs Work", 3: "Acceptable", 4: "Good", 5: "Excellent"},
        ),
        MemoForm(
            key="acceptance_criteria",
            label="Acceptance Criteria Description",
            instruction=(
                "Describe in detail what constitutes successful completion of this "
                "workflow. Be specific about measurable outcomes."
            ),
            min_length=30,
        ),
        ListForm(
            key="signoff_chain",
            label="Sign-Off Chain",
            instruction=(
                "Define the ordered chain of approvals required for final acceptance. "
                "Each entry is a role or person. Use ordering constraints to enforce "
                "the sequence (e.g., QA must sign off before Management)."
            ),
            allow_constraints=True,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Tab 6: Review — Notes & Readiness Checklist
# ---------------------------------------------------------------------------

review = GroupForm(
    key="review-group",
    label="Workflow Review",
    instruction=(
        "Use this tab to capture review notes and confirm readiness. "
        "Walk through the checklist to ensure all sections are complete, "
        "then record the review outcome."
    ),
    eigenforms=[
        CheckboxForm(
            key="review_checklist",
            label="Readiness Checklist",
            instruction=(
                "Confirm that each section of the workflow has been completed. "
                "Review the other tabs and check off each item as you verify it."
            ),
            items=[
                "Overview: name, description, type, and owner defined",
                "Stages: all pipeline stages added with types and gates assigned",
                "Gates: gate criteria defined for each stage transition",
                "Paths: parallel, conditional, and merge paths configured (if applicable)",
                "Acceptance: deliverables, approver, quality threshold, and sign-off chain set",
            ],
        ),
        ChoiceForm(
            key="review_outcome",
            label="Review Outcome",
            instruction="What is the overall assessment of this workflow definition?",
            options=[
                "Ready for Use",
                "Needs Revision",
                "Approved with Conditions",
                "Rejected",
            ],
        ),
        MemoForm(
            key="review_notes",
            label="Review Notes",
            instruction=(
                "Record any observations, concerns, or conditions from the review. "
                "Note any gaps that need to be addressed before the workflow is deployed."
            ),
            min_length=10,
        ),
    ],
)


# ---------------------------------------------------------------------------
# Page Definition
# ---------------------------------------------------------------------------

definition = PageForm(
    key="workflow-builder",
    label="Workflow Builder",
    instruction=(
        "Design a workflow with stage gates, parallel paths, conditional branches, "
        "merge gates, and final acceptance criteria. Work through the tabs from left "
        "to right, or jump to any section. The Review tab shows a live summary and "
        "validates structural consistency."
    ),
    eigenforms=[
        TabForm(
            key="builder",
            label="Builder",
            tabs={
                "overview": overview,
                "stages": stages,
                "gates": gates,
                "paths": paths,
                "acceptance": acceptance,
                "review": review,
            },
        ),
    ],
)
