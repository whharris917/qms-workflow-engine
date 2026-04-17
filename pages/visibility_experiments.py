"""Visibility Experiments — exploring conditional visibility patterns."""

from engine.choicecomponent import ChoiceComponent
from engine.checkboxcomponent import CheckboxComponent
from engine.textcomponent import TextComponent
from engine.pagecomponent import PageComponent
from engine.visibilitycomponent import VisibilityComponent


definition = PageComponent(key="visibility-experiments", label="Visibility Experiments", instruction="Experiments with conditional visibility.", components=[
    ChoiceComponent(key="mode", label="Mode", instruction="Select a mode.",
               options=["Simple", "Advanced", "Expert"]),
    VisibilityComponent(key="v-advanced", label="Advanced Options",
                   depends_on="mode", visible_when=["Advanced", "Expert"],
                   component=TextComponent(key="detail", label="Detail Level",
                                     instruction="How much detail do you want?")),
    VisibilityComponent(key="v-expert", label="Expert Options",
                   depends_on="mode", visible_when="Expert",
                   component=CheckboxComponent(key="flags", label="Expert Flags",
                                          instruction="Select expert features.",
                                          items=["debug", "verbose", "unsafe"])),
])
