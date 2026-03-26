"""Visibility Experiments — exploring conditional visibility patterns."""

from engine.choice import ChoiceForm
from engine.eigenforms import CheckboxForm, TextForm
from engine.page import PageForm
from engine.visibility import VisibilityForm


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
