"""Nested Tabs Test — quadruple-nested tab-mode NavigationForms."""

from engine.textform import TextForm
from engine.infoform import InfoForm
from engine.groupform import GroupForm
from engine.pageform import PageForm
from engine.navigationform import NavigationForm


def _leaf(prefix, breadcrumb):
    """Create a GroupForm leaf with an InfoForm breadcrumb and two TextForms."""
    return GroupForm(key=prefix, label=prefix.title(), instruction=f"GroupForm at {breadcrumb}.", editable=True, eigenforms=[
        InfoForm(key=f"{prefix}-info", label="Location", text=breadcrumb, editable=True),
        TextForm(key=f"{prefix}-t1", label=f"{prefix.title()} Field 1", instruction=f"First field in {breadcrumb}.", editable=True),
        TextForm(key=f"{prefix}-t2", label=f"{prefix.title()} Field 2", instruction=f"Second field in {breadcrumb}.", editable=True),
    ])


definition = PageForm(
    key="nested-tabs-test",
    label="Nested Tabs Test",
    instruction="Quadruple-nested NavigationForms for testing vertical/horizontal tab rendering.",
    eigenforms=[
        NavigationForm(key="level-1", label="Level 1", instruction="Level 1 instruction — top-level nav, should be vertical in Sleek.", mode="tabs", editable=True, steps=[
            GroupForm(key="alpha-grp", label="Alpha", instruction="Level 2 group (Alpha) — content for the Alpha tab.", editable=True, eigenforms=[
                NavigationForm(key="alpha", label="Alpha Nav", instruction="Level 2 nav (Alpha) — nested, should be horizontal.", mode="tabs", editable=True, steps=[
                    GroupForm(key="alpha-1-grp", label="Alpha-1", instruction="Level 3 group (Alpha-1).", editable=True, eigenforms=[
                        NavigationForm(key="alpha-1", label="Alpha-1 Nav", instruction="Level 3 nav (Alpha-1) — double-nested.", mode="tabs", editable=True, steps=[
                            GroupForm(key="alpha-1-a-grp", label="Alpha-1-A", instruction="Level 4 group (Alpha-1-A).", editable=True, eigenforms=[
                                NavigationForm(key="alpha-1-a", label="Alpha-1-A Nav", instruction="Level 4 nav (Alpha-1-A) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("a1a-x", "Alpha > Alpha-1 > Alpha-1-A > X"),
                                    _leaf("a1a-y", "Alpha > Alpha-1 > Alpha-1-A > Y"),
                                ]),
                            ]),
                            GroupForm(key="alpha-1-b-grp", label="Alpha-1-B", instruction="Level 4 group (Alpha-1-B).", editable=True, eigenforms=[
                                NavigationForm(key="alpha-1-b", label="Alpha-1-B Nav", instruction="Level 4 nav (Alpha-1-B) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("a1b-x", "Alpha > Alpha-1 > Alpha-1-B > X"),
                                    _leaf("a1b-y", "Alpha > Alpha-1 > Alpha-1-B > Y"),
                                ]),
                            ]),
                        ]),
                    ]),
                    GroupForm(key="alpha-2-grp", label="Alpha-2", instruction="Level 3 group (Alpha-2).", editable=True, eigenforms=[
                        NavigationForm(key="alpha-2", label="Alpha-2 Nav", instruction="Level 3 nav (Alpha-2) — double-nested.", mode="tabs", editable=True, steps=[
                            GroupForm(key="alpha-2-a-grp", label="Alpha-2-A", instruction="Level 4 group (Alpha-2-A).", editable=True, eigenforms=[
                                NavigationForm(key="alpha-2-a", label="Alpha-2-A Nav", instruction="Level 4 nav (Alpha-2-A) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("a2a-x", "Alpha > Alpha-2 > Alpha-2-A > X"),
                                    _leaf("a2a-y", "Alpha > Alpha-2 > Alpha-2-A > Y"),
                                ]),
                            ]),
                            GroupForm(key="alpha-2-b-grp", label="Alpha-2-B", instruction="Level 4 group (Alpha-2-B).", editable=True, eigenforms=[
                                NavigationForm(key="alpha-2-b", label="Alpha-2-B Nav", instruction="Level 4 nav (Alpha-2-B) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("a2b-x", "Alpha > Alpha-2 > Alpha-2-B > X"),
                                    _leaf("a2b-y", "Alpha > Alpha-2 > Alpha-2-B > Y"),
                                ]),
                            ]),
                        ]),
                    ]),
                ]),
            ]),
            GroupForm(key="beta-grp", label="Beta", instruction="Level 2 group (Beta) — content for the Beta tab.", editable=True, eigenforms=[
                NavigationForm(key="beta", label="Beta Nav", instruction="Level 2 nav (Beta) — nested, should be horizontal.", mode="tabs", editable=True, steps=[
                    GroupForm(key="beta-1-grp", label="Beta-1", instruction="Level 3 group (Beta-1).", editable=True, eigenforms=[
                        NavigationForm(key="beta-1", label="Beta-1 Nav", instruction="Level 3 nav (Beta-1) — double-nested.", mode="tabs", editable=True, steps=[
                            GroupForm(key="beta-1-a-grp", label="Beta-1-A", instruction="Level 4 group (Beta-1-A).", editable=True, eigenforms=[
                                NavigationForm(key="beta-1-a", label="Beta-1-A Nav", instruction="Level 4 nav (Beta-1-A) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("b1a-x", "Beta > Beta-1 > Beta-1-A > X"),
                                    _leaf("b1a-y", "Beta > Beta-1 > Beta-1-A > Y"),
                                ]),
                            ]),
                            GroupForm(key="beta-1-b-grp", label="Beta-1-B", instruction="Level 4 group (Beta-1-B).", editable=True, eigenforms=[
                                NavigationForm(key="beta-1-b", label="Beta-1-B Nav", instruction="Level 4 nav (Beta-1-B) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("b1b-x", "Beta > Beta-1 > Beta-1-B > X"),
                                    _leaf("b1b-y", "Beta > Beta-1 > Beta-1-B > Y"),
                                ]),
                            ]),
                        ]),
                    ]),
                    GroupForm(key="beta-2-grp", label="Beta-2", instruction="Level 3 group (Beta-2).", editable=True, eigenforms=[
                        NavigationForm(key="beta-2", label="Beta-2 Nav", instruction="Level 3 nav (Beta-2) — double-nested.", mode="tabs", editable=True, steps=[
                            GroupForm(key="beta-2-a-grp", label="Beta-2-A", instruction="Level 4 group (Beta-2-A).", editable=True, eigenforms=[
                                NavigationForm(key="beta-2-a", label="Beta-2-A Nav", instruction="Level 4 nav (Beta-2-A) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("b2a-x", "Beta > Beta-2 > Beta-2-A > X"),
                                    _leaf("b2a-y", "Beta > Beta-2 > Beta-2-A > Y"),
                                ]),
                            ]),
                            GroupForm(key="beta-2-b-grp", label="Beta-2-B", instruction="Level 4 group (Beta-2-B).", editable=True, eigenforms=[
                                NavigationForm(key="beta-2-b", label="Beta-2-B Nav", instruction="Level 4 nav (Beta-2-B) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("b2b-x", "Beta > Beta-2 > Beta-2-B > X"),
                                    _leaf("b2b-y", "Beta > Beta-2 > Beta-2-B > Y"),
                                ]),
                            ]),
                        ]),
                    ]),
                ]),
            ]),
            GroupForm(key="gamma-grp", label="Gamma", instruction="Level 2 group (Gamma) — content for the Gamma tab.", editable=True, eigenforms=[
                NavigationForm(key="gamma", label="Gamma Nav", instruction="Level 2 nav (Gamma) — nested, should be horizontal.", mode="tabs", editable=True, steps=[
                    GroupForm(key="gamma-1-grp", label="Gamma-1", instruction="Level 3 group (Gamma-1).", editable=True, eigenforms=[
                        NavigationForm(key="gamma-1", label="Gamma-1 Nav", instruction="Level 3 nav (Gamma-1) — double-nested.", mode="tabs", editable=True, steps=[
                            GroupForm(key="gamma-1-a-grp", label="Gamma-1-A", instruction="Level 4 group (Gamma-1-A).", editable=True, eigenforms=[
                                NavigationForm(key="gamma-1-a", label="Gamma-1-A Nav", instruction="Level 4 nav (Gamma-1-A) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("g1a-x", "Gamma > Gamma-1 > Gamma-1-A > X"),
                                    _leaf("g1a-y", "Gamma > Gamma-1 > Gamma-1-A > Y"),
                                ]),
                            ]),
                            GroupForm(key="gamma-1-b-grp", label="Gamma-1-B", instruction="Level 4 group (Gamma-1-B).", editable=True, eigenforms=[
                                NavigationForm(key="gamma-1-b", label="Gamma-1-B Nav", instruction="Level 4 nav (Gamma-1-B) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("g1b-x", "Gamma > Gamma-1 > Gamma-1-B > X"),
                                    _leaf("g1b-y", "Gamma > Gamma-1 > Gamma-1-B > Y"),
                                ]),
                            ]),
                        ]),
                    ]),
                    GroupForm(key="gamma-2-grp", label="Gamma-2", instruction="Level 3 group (Gamma-2).", editable=True, eigenforms=[
                        NavigationForm(key="gamma-2", label="Gamma-2 Nav", instruction="Level 3 nav (Gamma-2) — double-nested.", mode="tabs", editable=True, steps=[
                            GroupForm(key="gamma-2-a-grp", label="Gamma-2-A", instruction="Level 4 group (Gamma-2-A).", editable=True, eigenforms=[
                                NavigationForm(key="gamma-2-a", label="Gamma-2-A Nav", instruction="Level 4 nav (Gamma-2-A) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("g2a-x", "Gamma > Gamma-2 > Gamma-2-A > X"),
                                    _leaf("g2a-y", "Gamma > Gamma-2 > Gamma-2-A > Y"),
                                ]),
                            ]),
                            GroupForm(key="gamma-2-b-grp", label="Gamma-2-B", instruction="Level 4 group (Gamma-2-B).", editable=True, eigenforms=[
                                NavigationForm(key="gamma-2-b", label="Gamma-2-B Nav", instruction="Level 4 nav (Gamma-2-B) — triple-nested.", mode="tabs", editable=True, steps=[
                                    _leaf("g2b-x", "Gamma > Gamma-2 > Gamma-2-B > X"),
                                    _leaf("g2b-y", "Gamma > Gamma-2 > Gamma-2-B > Y"),
                                ]),
                            ]),
                        ]),
                    ]),
                ]),
            ]),
        ]),
    ],
)
