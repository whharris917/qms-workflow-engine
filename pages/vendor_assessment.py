"""Vendor Qualification Assessment — composes all eigenform primitives into a
realistic regulated-industry business workflow.

Exercises: AccordionForm, ChainForm, TabForm, VisibilityForm, MultiForm,
ChoiceForm, CheckboxForm, DateForm, BooleanForm,
NumberForm, TextForm, ListForm, DictionaryForm, TableForm, ComputedForm.
"""

from engine.booleanform import BooleanForm
from engine.choiceform import ChoiceForm
from engine.computedform import ComputedForm
from engine.dateform import DateForm
from engine.checkboxform import CheckboxForm
from engine.dictionaryform import DictionaryForm
from engine.textform import TextForm
from engine.multiform import FieldDescriptor, MultiForm
from engine.numberform import NumberForm
from engine.pageform import PageForm
from engine.listform import ListForm
from engine.navigationform import NavigationForm
from engine.tableform import TableForm
from engine.visibilityform import VisibilityForm


def compute_vendor_score(siblings):
    """Compute weighted average of ratings, scaled by confidence."""
    q = siblings.get("quality_rating")
    d = siblings.get("delivery_rating")
    p = siblings.get("pricing_rating")
    conf = siblings.get("confidence_level")
    if None in (q, d, p, conf):
        return {"status": "incomplete", "message": "Complete all ratings and confidence level first."}
    raw = q * 0.4 + d * 0.35 + p * 0.25
    adjusted = round(raw * (conf / 100), 2)
    if adjusted >= 3.0:
        recommendation = "Approve"
    elif adjusted >= 2.0:
        recommendation = "Review"
    else:
        recommendation = "Reject"
    return {
        "status": "computed",
        "raw_score": round(raw, 2),
        "confidence_percent": conf,
        "adjusted_score": adjusted,
        "recommendation": recommendation,
        "message": f"Score: {adjusted}/5.0 — {recommendation}",
    }


definition = PageForm(
    key="vendor-assessment",
    label="Vendor Qualification Assessment",
    instruction="Complete all sections to qualify a new vendor for the approved vendor list.",
    eigenforms=[
        # === Section 1: Collapsible vendor details ===
        NavigationForm(key="sections", label="Assessment Sections", mode="accordion", steps=[
            MultiForm(
                key="vendor_info", label="Vendor Information",
                instruction="Provide basic vendor identification.",
                fields=[
                    FieldDescriptor(key="company_name", label="Company Name"),
                    FieldDescriptor(key="contact_person", label="Primary Contact"),
                    FieldDescriptor(key="country", label="Country", type="choice",
                                    options=["United States", "Germany", "Japan", "China", "India", "Brazil", "Other"]),
                ]),

            NavigationForm(key="timeline", label="Assessment Timeline", mode="chain",
                        instruction="Complete each step in sequence.", steps=[
                DateForm(key="assessment_date", label="Assessment Date",
                         instruction="When is this assessment being conducted?"),
                DateForm(key="decision_deadline", label="Decision Deadline",
                         instruction="When must the qualification decision be made?"),
                ChoiceForm(key="vendor_type", label="Vendor Type",
                           instruction="What category does this vendor fall into?",
                           options=["Manufacturer", "Distributor", "Service Provider", "Raw Material Supplier"]),
                BooleanForm(key="existing_vendor", label="Existing Relationship?",
                            instruction="Has your organization previously done business with this vendor?",
                            true_label="Yes, existing vendor", false_label="No, new vendor"),
                VisibilityForm(key="v-history", label="Vendor History",
                               depends_on="existing_vendor", visible_when=True,
                               eigenform=TextForm(key="relationship_history",
                                                  label="Relationship History",
                                                  instruction="Describe your history with this vendor.",
                                                  multiline=True, min_length=50)),
            ]),

            NavigationForm(key="cap_tabs", label="Capability Assessment", mode="tabs",
                        instruction="Evaluate each capability area.", steps=[
                CheckboxForm(key="quality_certs", label="Quality Certifications",
                                        instruction="Select all certifications the vendor holds.",
                                        items=["ISO 9001", "ISO 14001", "ISO 45001", "GMP", "FDA Registered", "CE Marked"]),
                MultiForm(key="capacity_info", label="Production Capacity",
                                      fields=[
                                          FieldDescriptor(key="annual_revenue", label="Annual Revenue",
                                                          instruction="Approximate annual revenue"),
                                          FieldDescriptor(key="employee_count", label="Employee Count"),
                                          FieldDescriptor(key="lead_time", label="Typical Lead Time", type="choice",
                                                          options=["< 1 week", "1-2 weeks", "2-4 weeks", "1-2 months", "> 2 months"]),
                                      ]),
                BooleanForm(key="sanctions_check", label="Subject to Trade Sanctions?",
                            instruction="Is this vendor subject to any known trade sanctions or restrictions?",
                            true_label="Yes", false_label="No"),
            ]),
        ]),

        # === Section 2: Performance ratings ===
        NumberForm(key="quality_rating", label="Quality Rating",
                   instruction="Rate the vendor's quality system (1-5).",
                   min_val=1, max_val=5, step=1),
        NumberForm(key="delivery_rating", label="Delivery Reliability Rating",
                   instruction="Rate the vendor's delivery track record (1-5).",
                   min_val=1, max_val=5, step=1),
        NumberForm(key="pricing_rating", label="Pricing Competitiveness Rating",
                   instruction="Rate the vendor's pricing relative to market (1-5).",
                   min_val=1, max_val=5, step=1),
        NumberForm(key="confidence_level", label="Assessment Confidence",
                  instruction="How confident are you in the accuracy of this assessment?",
                  min_val=0, max_val=100, step=5, slider=True, unit="%"),

        # === Section 3: Financial ===
        NumberForm(key="proposed_credit_limit", label="Proposed Credit Limit ($)",
                   instruction="Recommended credit limit for purchase orders.",
                   min_val=0, max_val=10000000, step=1000),

        # === Section 4: Prioritization ===
        ListForm(key="priority_factors", label="Evaluation Priority Factors",
                 instruction="Reorder these factors by importance for this vendor relationship.",
                 fixed_items=["Price", "Quality", "Delivery Speed", "Technical Support", "Innovation"],
                 allow_constraints=False),

        # === Section 5: Risk assessment ===
        TableForm(key="risk_matrix", label="Risk Assessment Matrix",
                  instruction="Add rows for each identified risk. Columns: Risk, Likelihood, Impact, Mitigation."),

        # === Section 6: Written assessment ===
        TextForm(key="executive_summary", label="Executive Summary",
                 instruction="Write a summary of the vendor's strengths, weaknesses, and recommendation rationale.",
                 multiline=True, min_length=100),
        DictionaryForm(key="custom_observations", label="Additional Observations",
                     instruction="Add any supplementary observations as key-value pairs.",
                     key_label="Category", value_label="Detail"),

        # === Section 7: Computed score (reads sibling ratings) ===
        # MUST appear before the VisibilityForm below since store_result=True
        ComputedForm(key="vendor_score", label="Computed Vendor Score",
                     instruction="Automatically calculated from ratings and confidence level.",
                     depends_on=["quality_rating", "delivery_rating", "pricing_rating", "confidence_level"],
                     compute_fn=compute_vendor_score,
                     store_result=True),

        # === Section 8: Conditional approval (visible once score is computed) ===
        VisibilityForm(
            key="v-final-approval", label="Final Approval",
            depends_on="vendor_score",
            visible_when=lambda val: isinstance(val, dict) and val.get("status") == "computed",
            eigenform=ChoiceForm(
                key="approval_decision", label="Approval Decision",
                instruction="Based on the computed score and your assessment, make a final decision.",
                options=["Approved", "Conditionally Approved", "Rejected", "Deferred"],
            ),
        ),
    ],
)
