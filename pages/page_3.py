"""Page 3 — RubiksCubeForm showcase."""

from engine.page import PageForm
from engine.rubiks import RubiksCubeForm


definition = PageForm(key="page-3", label="Page 3", eigenforms=[
    RubiksCubeForm(key="cube", label="Rubik's Cube",
                   instruction="A fully functional cube. Rotate any face."),
])
