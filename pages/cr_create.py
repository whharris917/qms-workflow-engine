"""Create Change Record — initial scaffolding for the QMS's first real workflow.

Captures the pre-approved content of a Change Record per TEMPLATE-CR
(QMS/TEMPLATE/TEMPLATE-CR.md) and Quality Manual §04 (04-Change-Control.md):
sections 1–9 plus section 12 (References). Sections 10 (Execution) and 11
(Execution Summary) are written during and after execution and are not part
of the initial draft.

Submit is currently a stub. Razem has no terminal-execution primitive yet,
so this Action cannot invoke `qms create CR --title "..."` or perform the
checkout / write-content / checkin flow that minting a real CR requires.
The action_fn returns a preview of the CLI invocation that *would* run
once the primitive lands. This page is the diagnostic that motivates
building it.

Sections 7.4 (Development Controls), 7.5 (Qualified State Continuity), and
the code-specific implementation phases (Test Environment Setup,
Qualification, RTM Update, Merge & Submodule Update) are intentionally
omitted from this scaffold — they apply only to code CRs and depend on
sibling-of-tab visibility that the engine doesn't currently support across
container boundaries. They are tracked as future work.
"""

from engine.action import Action
from engine.choiceform import ChoiceForm
from engine.group import Group
from engine.infodisplay import InfoDisplay
from engine.listform import ListForm
from engine.navigation import Tabs
from engine.page import Page
from engine.tableform import TableForm
from engine.textform import TextForm
from engine.visibility import Visibility


# ---------------------------------------------------------------------------
# Submit (stub — returns the CLI invocation that would mint this CR)
# ---------------------------------------------------------------------------

def _submit_cr_draft(context: dict, store, scope: str) -> dict:
    """Preview what would happen if Razem could shell out to qms-cli.

    `context` carries the values of the Action's `depends_on` keys —
    page-level metadata fields (title, cr_type, parent_kind). Section
    content lives inside the Tabs container at a deeper scope and is
    not visible to this stub; once the terminal-execution primitive
    exists, the full action_fn will read every section, render the
    populated template body, and run the qms-cli sequence below.
    """
    title = (context.get("title") or "").strip()
    cr_type = context.get("cr_type") or "(unspecified)"
    parent_kind = context.get("parent_kind") or "None"
    return {
        "stub": True,
        "title": title,
        "cr_type": cr_type,
        "parent_kind": parent_kind,
        "would_invoke": [
            f'qms create CR --title "{title}"',
            "qms checkout CR-NNN",
            "(write the populated section bodies into the CR markdown)",
            "qms checkin CR-NNN",
        ],
        "note": (
            "Razem has no terminal-execution primitive yet, so this Submit "
            "captures the draft locally rather than minting a real CR. When "
            "the exec primitive lands, the action_fn will run the commands "
            "listed in 'would_invoke' in order and return the new CR ID."
        ),
    }


def _has_title(context: dict) -> bool:
    return bool((context.get("title") or "").strip())


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

definition = Page(
    key="cr-create",
    label="Create Change Record",
    instruction=(
        "Authoring scaffold for a new CR. The tabs below correspond to the "
        "pre-approved sections of TEMPLATE-CR (Quality Manual §04). Submit "
        "is a stub until Razem gains the ability to invoke qms-cli."
    ),
    components=[

        InfoDisplay(
            key="header",
            label="About a Change Record",
            text=(
                "A Change Record (CR) authorizes a single controlled change to "
                "the codebase or QMS. It is reviewed pre-execution, executed, "
                "then reviewed post-execution before closure. This page captures "
                "the pre-approved content (sections 1–9 plus 12 References). "
                "Sections 10 (Execution) and 11 (Execution Summary) are "
                "populated after pre-approval and are not part of this draft."
            ),
        ),

        # --- Document metadata (page-level so Submit's depends_on resolves) ---

        TextForm(
            key="title",
            label="Title",
            instruction=(
                "Short imperative phrase summarizing the change. "
                'e.g. "Add particle emitter configuration panel".'
            ),
            min_length=8,
            max_length=120,
        ),

        ChoiceForm(
            key="cr_type",
            label="CR type",
            instruction=(
                "Document-only CRs revise SOPs, templates, or other governed "
                "documents. Code CRs modify controlled code and require "
                "RS/RTM coordination plus a qualified merge to main. This "
                "scaffold captures content common to both — code-specific "
                "sections (7.4, 7.5, and the code-CR implementation phases) "
                "are not yet wired up."
            ),
            options=["Document-only CR", "Code CR"],
        ),

        ChoiceForm(
            key="parent_kind",
            label="Parent document",
            instruction=(
                "If this CR derives from an Investigation's CAPA, a VAR's "
                "resolution work, or another driving document, identify the "
                "kind. Independent improvements have no parent."
            ),
            options=[
                "None — independent change",
                "Investigation (INV)",
                "VAR",
                "Other",
            ],
        ),

        Visibility(
            key="parent_id_visibility",
            label="Parent document ID (visible when a parent kind is selected)",
            depends_on="parent_kind",
            visible_when=["Investigation (INV)", "VAR", "Other"],
            component=TextForm(
                key="parent_doc_id",
                label="Parent document ID",
                instruction='e.g. "INV-014" or "CR-091-VAR-001".',
            ),
        ),

        # --- Section authoring (Tabs: parallel — fill in any order) ---

        Tabs(
            key="sections",
            label="Pre-approved sections",
            instruction=(
                "Sections 1–9 of the CR per TEMPLATE-CR, plus 12 References. "
                "Tabs are parallel — fill in any order. All sections must be "
                "populated before routing for review."
            ),
            steps=[

                # 1. Purpose
                TextForm(
                    key="purpose",
                    label="1. Purpose",
                    instruction=(
                        "One sentence: WHAT this CR accomplishes. Keep it "
                        "crisp — justification (the WHY) goes in tab 6. "
                        "Example: \"Add a configuration panel for particle "
                        "emitter parameters.\""
                    ),
                    multiline=True,
                ),

                # 2. Scope
                Group(
                    key="scope",
                    label="2. Scope",
                    instruction=(
                        "Context, summary of changes, and files affected. "
                        "Per TEMPLATE-CR §2."
                    ),
                    components=[
                        TextForm(
                            key="context",
                            label="2.1 Context",
                            instruction=(
                                "What drives this change? Reference parent "
                                "INV/CAPA if any; otherwise describe the "
                                "origin (e.g. \"Independent improvement "
                                "identified during development\")."
                            ),
                            multiline=True,
                        ),
                        TextForm(
                            key="changes_summary",
                            label="2.2 Changes Summary",
                            instruction="Brief description of what will change.",
                            multiline=True,
                        ),
                        ListForm(
                            key="files_affected",
                            label="2.3 Files Affected",
                            instruction=(
                                "One entry per file or path with a brief "
                                "change description. The detailed table with "
                                "change types lives in tab 7."
                            ),
                        ),
                    ],
                ),

                # 3. Current State
                TextForm(
                    key="current_state",
                    label="3. Current State",
                    instruction=(
                        "What exists NOW. Present tense. Reviewers compare "
                        "this against tab 4 (Proposed State) to understand "
                        "exactly what changes — be specific about file "
                        "paths, function names, and configuration values."
                    ),
                    multiline=True,
                ),

                # 4. Proposed State
                TextForm(
                    key="proposed_state",
                    label="4. Proposed State",
                    instruction=(
                        "What will exist AFTER. Present tense. Forms a diff "
                        "pair with tab 3."
                    ),
                    multiline=True,
                ),

                # 5. Change Description
                TextForm(
                    key="change_description",
                    label="5. Change Description",
                    instruction=(
                        "Full technical details. Free-form structure based "
                        "on complexity. Reference file paths, function "
                        "names, configuration keys explicitly."
                    ),
                    multiline=True,
                ),

                # 6. Justification
                Group(
                    key="justification",
                    label="6. Justification",
                    instruction=(
                        "WHY this change is needed. Per TEMPLATE-CR §6 the "
                        "justification has three parts: the problem solved, "
                        "the impact of NOT making the change, and how the "
                        "proposed solution addresses the root cause."
                    ),
                    components=[
                        TextForm(
                            key="problem",
                            label="6.1 Problem solved / improvement made",
                            instruction=(
                                "What problem is this CR solving, or what "
                                "improvement is it introducing?"
                            ),
                            multiline=True,
                        ),
                        TextForm(
                            key="impact_if_skipped",
                            label="6.2 Impact of NOT making this change",
                            instruction=(
                                "What happens if this CR is never executed? "
                                "Helps reviewers gauge urgency and priority."
                            ),
                            multiline=True,
                        ),
                        TextForm(
                            key="addresses_root_cause",
                            label="6.3 How the proposed solution addresses the root cause",
                            instruction=(
                                "Per QMS-Policy §3, root-cause treatment is "
                                "preferred over symptom treatment. Explain "
                                "the link from problem → fix."
                            ),
                            multiline=True,
                        ),
                    ],
                ),

                # 7. Impact Assessment
                Group(
                    key="impact",
                    label="7. Impact Assessment",
                    instruction=(
                        "Broader consequences. Be thorough — this is what "
                        "reviewers use to identify hidden coupling. Per "
                        "Quality Manual §04, think about other code modules, "
                        "existing SOPs, the RS/RTM, and other open CRs that "
                        "might conflict."
                    ),
                    components=[
                        TableForm(
                            key="files_impact",
                            label="7.1 Files Affected",
                            instruction=(
                                "Each row: a file path, a change type "
                                "(Create / Modify / Delete), and a brief "
                                "description of the change."
                            ),
                            fixed_columns=["File", "Change Type", "Description"],
                        ),
                        TableForm(
                            key="documents_impact",
                            label="7.2 Documents Affected",
                            instruction=(
                                "QMS or external documents created or "
                                "modified by this change (e.g. SOPs, "
                                "templates, RS, RTM)."
                            ),
                            fixed_columns=["Document", "Change Type", "Description"],
                        ),
                        TextForm(
                            key="other_impacts",
                            label="7.3 Other Impacts",
                            instruction=(
                                "External systems, interfaces, dependencies, "
                                "or \"None\"."
                            ),
                            multiline=True,
                        ),
                    ],
                ),

                # 8. Testing Summary
                Group(
                    key="testing",
                    label="8. Testing Summary",
                    instruction=(
                        "How the change will be verified. Per SOP-002 §6.8, "
                        "code CRs must address both automated AND integration "
                        "verification."
                    ),
                    components=[
                        TextForm(
                            key="automated_testing",
                            label="8.1 Automated Verification",
                            instruction=(
                                "Unit tests, qualification tests, CI checks. "
                                "For document-only CRs, \"N/A\" or describe "
                                "procedural verification."
                            ),
                            multiline=True,
                        ),
                        TextForm(
                            key="integration_verification",
                            label="8.2 Integration Verification",
                            instruction=(
                                "What will be exercised through user-facing "
                                "levers in a running system to demonstrate "
                                "the change is effective. For document-only "
                                "CRs, \"N/A\"."
                            ),
                            multiline=True,
                        ),
                    ],
                ),

                # 9. Implementation Plan
                ListForm(
                    key="implementation_plan",
                    label="9. Implementation Plan",
                    instruction=(
                        "Ordered list of phases or steps. The execution "
                        "phase will populate sections 10 (EI table) and 11 "
                        "(Execution Summary) from this plan. For code CRs, "
                        "the standard phases per TEMPLATE-CR §9 are: Test "
                        "Environment Setup, Requirements (RS Update), "
                        "Implementation, Qualification, Integration "
                        "Verification, RTM Update, Merge & Submodule "
                        "Update, Documentation. For document-only CRs, the "
                        "relevant subset."
                    ),
                ),

                # 12. References
                ListForm(
                    key="references",
                    label="12. References",
                    instruction=(
                        "Related documents. At minimum, reference the "
                        "governing SOPs (SOP-001 Document Control and "
                        "SOP-002 Change Control). Add parent INV/VAR/CR, "
                        "downstream RS/RTM, and any external resources."
                    ),
                ),
            ],
        ),

        # --- Submit ---

        InfoDisplay(
            key="submit_notes",
            label="About Submit",
            text=(
                "Razem currently has no ability to execute external commands, "
                "so Submit cannot mint a real CR yet. Once a terminal-"
                "execution primitive lands, Submit will invoke "
                "`qms create CR --title \"...\"`, then check out the new "
                "draft, write the populated section bodies into it, and "
                "check it back in. For now, Submit captures a preview of "
                "what would happen and stores the draft data on this page."
            ),
        ),

        Action(
            key="submit",
            label="Submit",
            instruction=(
                "Capture the draft and preview the qms-cli invocation that "
                "would mint this CR."
            ),
            action_label="Create Change Record (stub)",
            depends_on=["title", "cr_type", "parent_kind"],
            action_fn=_submit_cr_draft,
            precondition_fn=_has_title,
            precondition_message="A title is required (minimum 8 characters).",
        ),
    ],
)
