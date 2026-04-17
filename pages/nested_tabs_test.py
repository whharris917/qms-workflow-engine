"""Nested Tabs Test — stress-test for container nesting, layout rules, and edge cases.

Layout rule under test: PageComponent > NavigationComponent (direct child) = vertical sidebar.
All other NavigationComponents = horizontal tabs/steps. GroupComponent dissolves when direct
child of NavigationComponent. This page exercises every combination we can think of.
"""

from engine.textcomponent import TextComponent
from engine.groupcomponent import GroupComponent
from engine.pagecomponent import PageComponent
from engine.navigationcomponent import NavigationComponent
from engine.checkboxcomponent import CheckboxComponent
from engine.booleancomponent import BooleanComponent
from engine.numbercomponent import NumberComponent
from engine.choicecomponent import ChoiceComponent
from engine.infocomponent import InfoComponent
from engine.listcomponent import ListComponent
from engine.switchcomponent import SwitchComponent
from engine.visibilitycomponent import VisibilityComponent


definition = PageComponent(
    key="nested-tabs-test",
    label="Nested Tabs Stress Test",
    instruction="Exercises vertical/horizontal layout rules, deep nesting, all four NavigationComponent modes, GroupComponent dissolve, and container edge cases.",
    components=[

        # ── TOP-LEVEL NAV: vertical sidebar (PageComponent > NavigationComponent) ─────
        NavigationComponent(key="main", label="Main Nav", instruction="Direct child of PageComponent — should be vertical sidebar.", mode="tabs", steps=[

            # ── Tab 1: All four nav modes nested inside tabs ────────────────
            GroupComponent(key="four-modes", label="Four Modes", instruction="Every NavigationComponent mode nested inside a vertical tab.", components=[

                NavigationComponent(key="nested-tabs", label="Nested Tabs", instruction="Horizontal tabs (nested, not direct child of PageComponent).", mode="tabs", steps=[
                    TextComponent(key="t1", label="Tab One", instruction="First tab content."),
                    TextComponent(key="t2", label="Tab Two", instruction="Second tab content."),
                    TextComponent(key="t3", label="Tab Three", instruction="Third tab content."),
                ]),

                NavigationComponent(key="nested-chain", label="Nested Chain", instruction="Gated chain with auto-advance.", mode="chain", steps=[
                    TextComponent(key="c1", label="Step 1", instruction="Complete to unlock step 2."),
                    BooleanComponent(key="c2", label="Step 2", instruction="Confirm to advance."),
                    TextComponent(key="c3", label="Step 3", instruction="Final chain step."),
                ]),

                NavigationComponent(key="nested-seq", label="Nested Sequence", instruction="Gated sequence with manual Back/Next.", mode="sequence", steps=[
                    CheckboxComponent(key="s1", label="Checklist A", instruction="Pick items.", items=["Alpha", "Beta", "Gamma"]),
                    CheckboxComponent(key="s2", label="Checklist B", instruction="Pick more.", items=["Delta", "Epsilon"]),
                ]),

                NavigationComponent(key="nested-acc", label="Nested Accordion", instruction="All sections visible, expand/collapse.", mode="accordion", default_expanded=False, steps=[
                    TextComponent(key="a1", label="Section A", instruction="Accordion section one."),
                    TextComponent(key="a2", label="Section B", instruction="Accordion section two."),
                    NumberComponent(key="a3", label="Section C", instruction="A number in an accordion.", min_val=0, max_val=100),
                ]),
            ]),

            # ── Tab 2: Deep nesting (3+ levels) ────────────────────────────
            NavigationComponent(key="deep", label="Deep Nesting", instruction="Horizontal tabs (level 2) containing more navigation.", mode="tabs", steps=[

                # Level 3: tabs inside tabs inside tabs
                NavigationComponent(key="deep-tabs", label="L3 Tabs", instruction="Third nesting level — still horizontal.", mode="tabs", steps=[
                    NavigationComponent(key="deep-tabs-inner", label="L4 Tabs", instruction="Fourth level — tabs all the way down.", mode="tabs", steps=[
                        TextComponent(key="abyss", label="The Abyss", instruction="Four levels deep."),
                        InfoComponent(key="abyss-info", label="Depth Check", text="If this renders as horizontal tabs, the layout rule is working."),
                    ]),
                    TextComponent(key="deep-sibling", label="L3 Sibling", instruction="Sibling of L4 nav at level 3."),
                ]),

                # Mixed modes at depth
                NavigationComponent(key="deep-chain", label="L3 Chain", instruction="Chain at third level.", mode="chain", steps=[
                    NavigationComponent(key="chain-inner-acc", label="L4 Accordion", instruction="Accordion inside a chain step.", mode="accordion", steps=[
                        TextComponent(key="cia1", label="Acc Section 1", instruction="Accordion in chain in tabs in tabs."),
                        TextComponent(key="cia2", label="Acc Section 2", instruction="Second section."),
                    ]),
                    TextComponent(key="chain-step-2", label="Chain Step 2", instruction="After the accordion step."),
                ]),

                # Sequence containing a chain containing tabs
                NavigationComponent(key="deep-mix", label="L3 Seq>Chain>Tabs", instruction="Sequence wrapping a chain wrapping tabs.", mode="sequence", steps=[
                    NavigationComponent(key="mix-chain", label="Inner Chain", instruction="Chain inside sequence.", mode="chain", steps=[
                        NavigationComponent(key="mix-tabs", label="Innermost Tabs", instruction="Tabs inside chain inside sequence.", mode="tabs", steps=[
                            TextComponent(key="mix-a", label="Mix A"),
                            TextComponent(key="mix-b", label="Mix B"),
                        ]),
                        TextComponent(key="mix-after", label="After Tabs", instruction="Step after the inner tabs."),
                    ]),
                    TextComponent(key="mix-final", label="Sequence End", instruction="Last step of the outer sequence."),
                ]),
            ]),

            # ── Tab 3: GroupComponent behavior ───────────────────────────────────
            GroupComponent(key="group-tests", label="GroupComponent Tests", instruction="Tests GroupComponent dissolve and nesting behavior.", components=[

                InfoComponent(key="group-info", label="GroupComponent Rules", text={
                    "Dissolve rule": "GroupComponent dissolves (no border) when direct child of NavigationComponent",
                    "Nested group": "GroupComponent inside GroupComponent should both render with their own styling",
                    "Nav inside group": "NavigationComponent inside GroupComponent should be horizontal",
                }),

                # GroupComponent containing another GroupComponent
                GroupComponent(key="inner-group", label="Inner Group", instruction="A GroupComponent nested inside another GroupComponent.", components=[
                    TextComponent(key="ig1", label="Inner Field 1", instruction="Field inside nested group."),
                    TextComponent(key="ig2", label="Inner Field 2", instruction="Another field."),
                ]),

                # GroupComponent containing navigation
                GroupComponent(key="group-with-nav", label="Group With Nav", instruction="NavigationComponent inside a GroupComponent — should be horizontal.", components=[
                    NavigationComponent(key="group-nav", label="Nav In Group", mode="tabs", steps=[
                        TextComponent(key="gn1", label="Tab 1"),
                        TextComponent(key="gn2", label="Tab 2"),
                    ]),
                ]),

                # NavigationComponent containing a GroupComponent (dissolve test)
                NavigationComponent(key="nav-with-group", label="Nav With Group", instruction="GroupComponent as direct child of NavigationComponent — should dissolve.", mode="tabs", steps=[
                    GroupComponent(key="dissolve-me", label="Dissolve Test", instruction="This GroupComponent should dissolve (no border/chrome).", components=[
                        TextComponent(key="dm1", label="Dissolved Field 1"),
                        TextComponent(key="dm2", label="Dissolved Field 2"),
                    ]),
                    GroupComponent(key="dissolve-me-too", label="Also Dissolve", instruction="Second GroupComponent tab — also dissolves.", components=[
                        BooleanComponent(key="dmt1", label="A Boolean", instruction="Inside dissolved group."),
                    ]),
                ]),
            ]),

            # ── Tab 4: Single-child and edge cases ─────────────────────────
            GroupComponent(key="edge-cases", label="Edge Cases", instruction="Unusual but valid configurations.", components=[

                # Single-child NavigationComponent
                NavigationComponent(key="single-tab", label="Single Tab Nav", instruction="NavigationComponent with only one child — tab bar should still render.", mode="tabs", steps=[
                    TextComponent(key="lonely", label="The Only Tab", instruction="Solo tab content."),
                ]),

                # Single-child chain
                NavigationComponent(key="single-chain", label="Single Step Chain", instruction="Chain with one step — should be immediately active.", mode="chain", steps=[
                    TextComponent(key="only-step", label="Only Step", instruction="The sole chain step."),
                ]),

                # Single-child accordion
                NavigationComponent(key="single-acc", label="Single Accordion", instruction="One section accordion.", mode="accordion", default_expanded=True, steps=[
                    TextComponent(key="only-section", label="Only Section", instruction="Lone accordion section."),
                ]),

                # Data form directly in top-level nav (not wrapped in group)
                InfoComponent(key="bare-info", label="Bare InfoComponent", text="This InfoComponent is a direct child of the edge-cases GroupComponent, not wrapped in any NavigationComponent."),

                # Accordion with mixed content types
                NavigationComponent(key="mixed-types-acc", label="Mixed Types Accordion", instruction="Each section is a different component type.", mode="accordion", default_expanded=False, steps=[
                    TextComponent(key="mta-text", label="Text Section", instruction="A text field."),
                    NumberComponent(key="mta-num", label="Number Section", instruction="A slider.", slider=True, min_val=0, max_val=50, unit="units"),
                    CheckboxComponent(key="mta-check", label="Checkbox Section", instruction="Pick things.", items=["One", "Two", "Three"]),
                    BooleanComponent(key="mta-bool", label="Boolean Section", instruction="Yes or no."),
                    ListComponent(key="mta-list", label="List Section", instruction="An ordered list."),
                ]),
            ]),

            # ── Tab 5: Reactive containers (Switch + Visibility) ───────────
            GroupComponent(key="reactive", label="Reactive Containers", instruction="SwitchComponent and VisibilityComponent inside navigation.", components=[

                ChoiceComponent(key="view-mode", label="View Mode", instruction="Pick a layout.", options=["Simple", "Detailed", "Advanced"]),

                # SwitchComponent that swaps entire navigation structures
                SwitchComponent(key="mode-switch", label="Mode Switch", depends_on="view-mode", cases={
                    "Simple": InfoComponent(key="simple-view", label="Simple", text="Minimal view — just an InfoComponent."),
                    "Detailed": NavigationComponent(key="detail-nav", label="Detail Tabs", mode="tabs", steps=[
                        TextComponent(key="d1", label="Detail A", instruction="First detail tab."),
                        TextComponent(key="d2", label="Detail B", instruction="Second detail tab."),
                    ]),
                    "Advanced": NavigationComponent(key="adv-nav", label="Advanced Tabs", mode="tabs", steps=[
                        NavigationComponent(key="adv-inner", label="Sub-Navigation", mode="sequence", steps=[
                            TextComponent(key="adv1", label="Step 1", instruction="Advanced step 1."),
                            TextComponent(key="adv2", label="Step 2", instruction="Advanced step 2."),
                            TextComponent(key="adv3", label="Step 3", instruction="Advanced step 3."),
                        ]),
                        GroupComponent(key="adv-config", label="Configuration", components=[
                            NumberComponent(key="adv-n1", label="Threshold", min_val=0, max_val=100, step=5),
                            BooleanComponent(key="adv-b1", label="Enabled"),
                        ]),
                    ]),
                }),

                # VisibilityComponent controlling a nested NavigationComponent
                VisibilityComponent(
                    key="conditional-nav",
                    label="Conditional Navigation",
                    depends_on="view-mode",
                    visible_when="Advanced",
                    component=NavigationComponent(key="vis-nav", label="Advanced-Only Nav", instruction="Only visible when Advanced is selected.", mode="accordion", steps=[
                        TextComponent(key="vn1", label="Extra Config A"),
                        TextComponent(key="vn2", label="Extra Config B"),
                    ]),
                ),
            ]),

            # ── Tab 6: Wide containers (many children) ─────────────────────
            GroupComponent(key="wide", label="Wide Containers", instruction="NavigationComponents with many children to test tab overflow and scrolling.", components=[

                NavigationComponent(key="many-tabs", label="Many Tabs (8)", instruction="Eight tabs — tests horizontal overflow.", mode="tabs", steps=[
                    TextComponent(key="w1", label="Tab 1"),
                    TextComponent(key="w2", label="Tab 2"),
                    TextComponent(key="w3", label="Tab 3"),
                    TextComponent(key="w4", label="Tab 4"),
                    TextComponent(key="w5", label="Tab 5"),
                    TextComponent(key="w6", label="Tab 6"),
                    TextComponent(key="w7", label="Tab 7"),
                    TextComponent(key="w8", label="Tab 8"),
                ]),

                NavigationComponent(key="many-acc", label="Many Sections (6)", instruction="Six accordion sections.", mode="accordion", default_expanded=False, steps=[
                    InfoComponent(key="ma1", label="Section 1", text="Content one."),
                    InfoComponent(key="ma2", label="Section 2", text="Content two."),
                    InfoComponent(key="ma3", label="Section 3", text="Content three."),
                    InfoComponent(key="ma4", label="Section 4", text="Content four."),
                    InfoComponent(key="ma5", label="Section 5", text="Content five."),
                    InfoComponent(key="ma6", label="Section 6", text="Content six."),
                ]),

                NavigationComponent(key="long-chain", label="Long Chain (5)", instruction="Five-step chain.", mode="chain", steps=[
                    TextComponent(key="lc1", label="Step 1"),
                    TextComponent(key="lc2", label="Step 2"),
                    TextComponent(key="lc3", label="Step 3"),
                    TextComponent(key="lc4", label="Step 4"),
                    TextComponent(key="lc5", label="Step 5"),
                ]),
            ]),
        ]),

        # ── SECOND TOP-LEVEL NAV: also vertical sidebar ────────────────────
        # Two direct PageComponent children — both should get vertical layout.
        NavigationComponent(key="secondary", label="Secondary Nav", instruction="Second direct child of PageComponent — also vertical sidebar.", mode="tabs", steps=[

            GroupComponent(key="sec-basics", label="Parallel Sidebar", instruction="Proves two top-level NavigationComponents coexist.", components=[
                InfoComponent(key="sec-info", label="Layout Verification", text={
                    "This NavigationComponent": "Direct child of PageComponent — vertical sidebar",
                    "The main NavigationComponent above": "Also direct child — also vertical sidebar",
                    "Rule": "ALL direct PageComponent > NavigationComponent children get vertical layout",
                }),
                TextComponent(key="sec-field", label="A Field", instruction="Simple field in the secondary sidebar."),
            ]),

            # Tabs inside the second top-level nav (should be horizontal)
            NavigationComponent(key="sec-nested", label="Nested In Secondary", instruction="Horizontal tabs inside second vertical sidebar.", mode="tabs", steps=[
                TextComponent(key="sn1", label="Tab A"),
                TextComponent(key="sn2", label="Tab B"),
            ]),
        ]),

        # ── BARE DATA FORM: not inside any NavigationComponent ──────────────────
        InfoComponent(key="footer-info", label="Footer", text="This InfoComponent sits at the top level of the PageComponent, outside any NavigationComponent. It should render as a normal card, not inside any sidebar."),
    ],
)
