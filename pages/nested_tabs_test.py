"""Nested Tabs Test — stress-test for container nesting, layout rules, and edge cases.

Layout rule under test: Page > Navigation (direct child) = vertical sidebar.
All other NavigationComponents = horizontal tabs/steps. Group dissolves when direct
child of Navigation. This page exercises every combination we can think of.
"""

from engine.textform import TextForm
from engine.group import Group
from engine.page import Page
from engine.navigation import Navigation
from engine.checkboxform import CheckboxForm
from engine.booleanform import BooleanForm
from engine.numberform import NumberForm
from engine.choiceform import ChoiceForm
from engine.infodisplay import InfoDisplay
from engine.listform import ListForm
from engine.switch import Switch
from engine.visibility import Visibility


definition = Page(
    key="nested-tabs-test",
    label="Nested Tabs Stress Test",
    instruction="Exercises vertical/horizontal layout rules, deep nesting, all four Navigation modes, Group dissolve, and container edge cases.",
    components=[

        # ── TOP-LEVEL NAV: vertical sidebar (Page > Navigation) ─────
        Navigation(key="main", label="Main Nav", instruction="Direct child of Page — should be vertical sidebar.", mode="tabs", steps=[

            # ── Tab 1: All four nav modes nested inside tabs ────────────────
            Group(key="four-modes", label="Four Modes", instruction="Every Navigation mode nested inside a vertical tab.", components=[

                Navigation(key="nested-tabs", label="Nested Tabs", instruction="Horizontal tabs (nested, not direct child of Page).", mode="tabs", steps=[
                    TextForm(key="t1", label="Tab One", instruction="First tab content."),
                    TextForm(key="t2", label="Tab Two", instruction="Second tab content."),
                    TextForm(key="t3", label="Tab Three", instruction="Third tab content."),
                ]),

                Navigation(key="nested-chain", label="Nested Chain", instruction="Gated chain with auto-advance.", mode="chain", steps=[
                    TextForm(key="c1", label="Step 1", instruction="Complete to unlock step 2."),
                    BooleanForm(key="c2", label="Step 2", instruction="Confirm to advance."),
                    TextForm(key="c3", label="Step 3", instruction="Final chain step."),
                ]),

                Navigation(key="nested-seq", label="Nested Sequence", instruction="Gated sequence with manual Back/Next.", mode="sequence", steps=[
                    CheckboxForm(key="s1", label="Checklist A", instruction="Pick items.", items=["Alpha", "Beta", "Gamma"]),
                    CheckboxForm(key="s2", label="Checklist B", instruction="Pick more.", items=["Delta", "Epsilon"]),
                ]),

                Navigation(key="nested-acc", label="Nested Accordion", instruction="All sections visible, expand/collapse.", mode="accordion", default_expanded=False, steps=[
                    TextForm(key="a1", label="Section A", instruction="Accordion section one."),
                    TextForm(key="a2", label="Section B", instruction="Accordion section two."),
                    NumberForm(key="a3", label="Section C", instruction="A number in an accordion.", min_val=0, max_val=100),
                ]),
            ]),

            # ── Tab 2: Deep nesting (3+ levels) ────────────────────────────
            Navigation(key="deep", label="Deep Nesting", instruction="Horizontal tabs (level 2) containing more navigation.", mode="tabs", steps=[

                # Level 3: tabs inside tabs inside tabs
                Navigation(key="deep-tabs", label="L3 Tabs", instruction="Third nesting level — still horizontal.", mode="tabs", steps=[
                    Navigation(key="deep-tabs-inner", label="L4 Tabs", instruction="Fourth level — tabs all the way down.", mode="tabs", steps=[
                        TextForm(key="abyss", label="The Abyss", instruction="Four levels deep."),
                        InfoDisplay(key="abyss-info", label="Depth Check", text="If this renders as horizontal tabs, the layout rule is working."),
                    ]),
                    TextForm(key="deep-sibling", label="L3 Sibling", instruction="Sibling of L4 nav at level 3."),
                ]),

                # Mixed modes at depth
                Navigation(key="deep-chain", label="L3 Chain", instruction="Chain at third level.", mode="chain", steps=[
                    Navigation(key="chain-inner-acc", label="L4 Accordion", instruction="Accordion inside a chain step.", mode="accordion", steps=[
                        TextForm(key="cia1", label="Acc Section 1", instruction="Accordion in chain in tabs in tabs."),
                        TextForm(key="cia2", label="Acc Section 2", instruction="Second section."),
                    ]),
                    TextForm(key="chain-step-2", label="Chain Step 2", instruction="After the accordion step."),
                ]),

                # Sequence containing a chain containing tabs
                Navigation(key="deep-mix", label="L3 Seq>Chain>Tabs", instruction="Sequence wrapping a chain wrapping tabs.", mode="sequence", steps=[
                    Navigation(key="mix-chain", label="Inner Chain", instruction="Chain inside sequence.", mode="chain", steps=[
                        Navigation(key="mix-tabs", label="Innermost Tabs", instruction="Tabs inside chain inside sequence.", mode="tabs", steps=[
                            TextForm(key="mix-a", label="Mix A"),
                            TextForm(key="mix-b", label="Mix B"),
                        ]),
                        TextForm(key="mix-after", label="After Tabs", instruction="Step after the inner tabs."),
                    ]),
                    TextForm(key="mix-final", label="Sequence End", instruction="Last step of the outer sequence."),
                ]),
            ]),

            # ── Tab 3: Group behavior ───────────────────────────────────
            Group(key="group-tests", label="Group Tests", instruction="Tests Group dissolve and nesting behavior.", components=[

                InfoDisplay(key="group-info", label="Group Rules", text={
                    "Dissolve rule": "Group dissolves (no border) when direct child of Navigation",
                    "Nested group": "Group inside Group should both render with their own styling",
                    "Nav inside group": "Navigation inside Group should be horizontal",
                }),

                # Group containing another Group
                Group(key="inner-group", label="Inner Group", instruction="A Group nested inside another Group.", components=[
                    TextForm(key="ig1", label="Inner Field 1", instruction="Field inside nested group."),
                    TextForm(key="ig2", label="Inner Field 2", instruction="Another field."),
                ]),

                # Group containing navigation
                Group(key="group-with-nav", label="Group With Nav", instruction="Navigation inside a Group — should be horizontal.", components=[
                    Navigation(key="group-nav", label="Nav In Group", mode="tabs", steps=[
                        TextForm(key="gn1", label="Tab 1"),
                        TextForm(key="gn2", label="Tab 2"),
                    ]),
                ]),

                # Navigation containing a Group (dissolve test)
                Navigation(key="nav-with-group", label="Nav With Group", instruction="Group as direct child of Navigation — should dissolve.", mode="tabs", steps=[
                    Group(key="dissolve-me", label="Dissolve Test", instruction="This Group should dissolve (no border/chrome).", components=[
                        TextForm(key="dm1", label="Dissolved Field 1"),
                        TextForm(key="dm2", label="Dissolved Field 2"),
                    ]),
                    Group(key="dissolve-me-too", label="Also Dissolve", instruction="Second Group tab — also dissolves.", components=[
                        BooleanForm(key="dmt1", label="A Boolean", instruction="Inside dissolved group."),
                    ]),
                ]),
            ]),

            # ── Tab 4: Single-child and edge cases ─────────────────────────
            Group(key="edge-cases", label="Edge Cases", instruction="Unusual but valid configurations.", components=[

                # Single-child Navigation
                Navigation(key="single-tab", label="Single Tab Nav", instruction="Navigation with only one child — tab bar should still render.", mode="tabs", steps=[
                    TextForm(key="lonely", label="The Only Tab", instruction="Solo tab content."),
                ]),

                # Single-child chain
                Navigation(key="single-chain", label="Single Step Chain", instruction="Chain with one step — should be immediately active.", mode="chain", steps=[
                    TextForm(key="only-step", label="Only Step", instruction="The sole chain step."),
                ]),

                # Single-child accordion
                Navigation(key="single-acc", label="Single Accordion", instruction="One section accordion.", mode="accordion", default_expanded=True, steps=[
                    TextForm(key="only-section", label="Only Section", instruction="Lone accordion section."),
                ]),

                # Data form directly in top-level nav (not wrapped in group)
                InfoDisplay(key="bare-info", label="Bare InfoDisplay", text="This InfoDisplay is a direct child of the edge-cases Group, not wrapped in any Navigation."),

                # Accordion with mixed content types
                Navigation(key="mixed-types-acc", label="Mixed Types Accordion", instruction="Each section is a different component type.", mode="accordion", default_expanded=False, steps=[
                    TextForm(key="mta-text", label="Text Section", instruction="A text field."),
                    NumberForm(key="mta-num", label="Number Section", instruction="A slider.", slider=True, min_val=0, max_val=50, unit="units"),
                    CheckboxForm(key="mta-check", label="Checkbox Section", instruction="Pick things.", items=["One", "Two", "Three"]),
                    BooleanForm(key="mta-bool", label="Boolean Section", instruction="Yes or no."),
                    ListForm(key="mta-list", label="List Section", instruction="An ordered list."),
                ]),
            ]),

            # ── Tab 5: Reactive containers (Switch + Visibility) ───────────
            Group(key="reactive", label="Reactive Containers", instruction="Switch and Visibility inside navigation.", components=[

                ChoiceForm(key="view-mode", label="View Mode", instruction="Pick a layout.", options=["Simple", "Detailed", "Advanced"]),

                # Switch that swaps entire navigation structures
                Switch(key="mode-switch", label="Mode Switch", depends_on="view-mode", cases={
                    "Simple": InfoDisplay(key="simple-view", label="Simple", text="Minimal view — just an InfoDisplay."),
                    "Detailed": Navigation(key="detail-nav", label="Detail Tabs", mode="tabs", steps=[
                        TextForm(key="d1", label="Detail A", instruction="First detail tab."),
                        TextForm(key="d2", label="Detail B", instruction="Second detail tab."),
                    ]),
                    "Advanced": Navigation(key="adv-nav", label="Advanced Tabs", mode="tabs", steps=[
                        Navigation(key="adv-inner", label="Sub-Navigation", mode="sequence", steps=[
                            TextForm(key="adv1", label="Step 1", instruction="Advanced step 1."),
                            TextForm(key="adv2", label="Step 2", instruction="Advanced step 2."),
                            TextForm(key="adv3", label="Step 3", instruction="Advanced step 3."),
                        ]),
                        Group(key="adv-config", label="Configuration", components=[
                            NumberForm(key="adv-n1", label="Threshold", min_val=0, max_val=100, step=5),
                            BooleanForm(key="adv-b1", label="Enabled"),
                        ]),
                    ]),
                }),

                # Visibility controlling a nested Navigation
                Visibility(
                    key="conditional-nav",
                    label="Conditional Navigation",
                    depends_on="view-mode",
                    visible_when="Advanced",
                    component=Navigation(key="vis-nav", label="Advanced-Only Nav", instruction="Only visible when Advanced is selected.", mode="accordion", steps=[
                        TextForm(key="vn1", label="Extra Config A"),
                        TextForm(key="vn2", label="Extra Config B"),
                    ]),
                ),
            ]),

            # ── Tab 6: Wide containers (many children) ─────────────────────
            Group(key="wide", label="Wide Containers", instruction="NavigationComponents with many children to test tab overflow and scrolling.", components=[

                Navigation(key="many-tabs", label="Many Tabs (8)", instruction="Eight tabs — tests horizontal overflow.", mode="tabs", steps=[
                    TextForm(key="w1", label="Tab 1"),
                    TextForm(key="w2", label="Tab 2"),
                    TextForm(key="w3", label="Tab 3"),
                    TextForm(key="w4", label="Tab 4"),
                    TextForm(key="w5", label="Tab 5"),
                    TextForm(key="w6", label="Tab 6"),
                    TextForm(key="w7", label="Tab 7"),
                    TextForm(key="w8", label="Tab 8"),
                ]),

                Navigation(key="many-acc", label="Many Sections (6)", instruction="Six accordion sections.", mode="accordion", default_expanded=False, steps=[
                    InfoDisplay(key="ma1", label="Section 1", text="Content one."),
                    InfoDisplay(key="ma2", label="Section 2", text="Content two."),
                    InfoDisplay(key="ma3", label="Section 3", text="Content three."),
                    InfoDisplay(key="ma4", label="Section 4", text="Content four."),
                    InfoDisplay(key="ma5", label="Section 5", text="Content five."),
                    InfoDisplay(key="ma6", label="Section 6", text="Content six."),
                ]),

                Navigation(key="long-chain", label="Long Chain (5)", instruction="Five-step chain.", mode="chain", steps=[
                    TextForm(key="lc1", label="Step 1"),
                    TextForm(key="lc2", label="Step 2"),
                    TextForm(key="lc3", label="Step 3"),
                    TextForm(key="lc4", label="Step 4"),
                    TextForm(key="lc5", label="Step 5"),
                ]),
            ]),
        ]),

        # ── SECOND TOP-LEVEL NAV: also vertical sidebar ────────────────────
        # Two direct Page children — both should get vertical layout.
        Navigation(key="secondary", label="Secondary Nav", instruction="Second direct child of Page — also vertical sidebar.", mode="tabs", steps=[

            Group(key="sec-basics", label="Parallel Sidebar", instruction="Proves two top-level NavigationComponents coexist.", components=[
                InfoDisplay(key="sec-info", label="Layout Verification", text={
                    "This Navigation": "Direct child of Page — vertical sidebar",
                    "The main Navigation above": "Also direct child — also vertical sidebar",
                    "Rule": "ALL direct Page > Navigation children get vertical layout",
                }),
                TextForm(key="sec-field", label="A Field", instruction="Simple field in the secondary sidebar."),
            ]),

            # Tabs inside the second top-level nav (should be horizontal)
            Navigation(key="sec-nested", label="Nested In Secondary", instruction="Horizontal tabs inside second vertical sidebar.", mode="tabs", steps=[
                TextForm(key="sn1", label="Tab A"),
                TextForm(key="sn2", label="Tab B"),
            ]),
        ]),

        # ── BARE DATA FORM: not inside any Navigation ──────────────────
        InfoDisplay(key="footer-info", label="Footer", text="This InfoDisplay sits at the top level of the Page, outside any Navigation. It should render as a normal card, not inside any sidebar."),
    ],
)
