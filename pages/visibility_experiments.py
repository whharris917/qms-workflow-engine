"""Visibility Experiments — exploring conditional visibility patterns."""

from engine.choiceform import ChoiceForm
from engine.checkboxform import CheckboxForm
from engine.textform import TextForm
from engine.pageform import PageForm
from engine.visibilityform import VisibilityForm


definition = PageForm(key="visibility-experiments", label="Visibility Experiments", instruction="Experiments with conditional visibility.", eigenforms=[
    ChoiceForm(key="mode", label="Mode", instruction="Select a mode.",
               options=["Simple", "Advanced", "Expert"]),
    VisibilityForm(key="v-advanced", label="Advanced Options",
                   depends_on="mode", visible_when=["Advanced", "Expert"],
                   eigenform=TextForm(key="detail", label="Detail Level",
                                     instruction="How much detail do you want?")),
    VisibilityForm(key="v-expert", label="Expert Options",
                   depends_on="mode", visible_when="Expert",
                   eigenform=CheckboxForm(key="flags", label="Expert Flags",
                                          instruction="Select expert features.",
                                          items=["debug", "verbose", "unsafe"])),
])
