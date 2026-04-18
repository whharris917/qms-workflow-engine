"""Visibility Experiments — exploring conditional visibility patterns."""

from engine.choiceform import ChoiceForm
from engine.checkboxform import CheckboxForm
from engine.textform import TextForm
from engine.page import Page
from engine.visibility import Visibility


definition = Page(key="visibility-experiments", label="Visibility Experiments", instruction="Experiments with conditional visibility.", components=[
    ChoiceForm(key="mode", label="Mode", instruction="Select a mode.",
               options=["Simple", "Advanced", "Expert"]),
    Visibility(key="v-advanced", label="Advanced Options",
                   depends_on="mode", visible_when=["Advanced", "Expert"],
                   component=TextForm(key="detail", label="Detail Level",
                                     instruction="How much detail do you want?")),
    Visibility(key="v-expert", label="Expert Options",
                   depends_on="mode", visible_when="Expert",
                   component=CheckboxForm(key="flags", label="Expert Flags",
                                          instruction="Select expert features.",
                                          items=["debug", "verbose", "unsafe"])),
])
