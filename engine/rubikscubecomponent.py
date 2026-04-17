"""RubiksCubeComponent — an arbitrarily complex component that is a complete
self-contained HATEOAS-compliant application.

Demonstrates that the component protocol imposes no limit on internal
complexity. The protocol says: you have state, you can serialize it,
you can render it, you can expose actions that mutate it.
"""

from __future__ import annotations

import copy
import json
import random
from dataclasses import dataclass
from typing import Any

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.component import Component
from engine.templates import render_template
from engine.store import Store

# Face indices in the state array
U, D, L, R, F, B = 'U', 'D', 'L', 'R', 'F', 'B'

# Solved state: each face is 9 stickers of one color
SOLVED = {
    U: ['W'] * 9,
    D: ['Y'] * 9,
    L: ['O'] * 9,
    R: ['R'] * 9,
    F: ['G'] * 9,
    B: ['B'] * 9,
}

COLORS = {
    'W': '#ffffff', 'Y': '#ffdd00', 'O': '#ff8800',
    'R': '#cc0000', 'G': '#00aa00', 'B': '#0044cc',
}


def _rotate_face_cw(face: list[str]) -> list[str]:
    """Rotate a 3x3 face 90° clockwise."""
    return [face[6], face[3], face[0],
            face[7], face[4], face[1],
            face[8], face[5], face[2]]


def _rotate_face_ccw(face: list[str]) -> list[str]:
    """Rotate a 3x3 face 90° counter-clockwise."""
    return [face[2], face[5], face[8],
            face[1], face[4], face[7],
            face[0], face[3], face[6]]


def _apply_rotation(cube: dict, face: str, direction: str) -> dict:
    """Apply a rotation to a cube state. Returns a new cube."""
    c = {k: list(v) for k, v in cube.items()}

    if direction == 'cw':
        c[face] = _rotate_face_cw(c[face])
    else:
        c[face] = _rotate_face_ccw(c[face])

    # Cycle the adjacent edge strips
    if face == U:
        if direction == 'cw':
            t = c[F][0:3]
            c[F][0:3] = c[R][0:3]
            c[R][0:3] = c[B][0:3]
            c[B][0:3] = c[L][0:3]
            c[L][0:3] = t
        else:
            t = c[F][0:3]
            c[F][0:3] = c[L][0:3]
            c[L][0:3] = c[B][0:3]
            c[B][0:3] = c[R][0:3]
            c[R][0:3] = t
    elif face == D:
        if direction == 'cw':
            t = c[F][6:9]
            c[F][6:9] = c[L][6:9]
            c[L][6:9] = c[B][6:9]
            c[B][6:9] = c[R][6:9]
            c[R][6:9] = t
        else:
            t = c[F][6:9]
            c[F][6:9] = c[R][6:9]
            c[R][6:9] = c[B][6:9]
            c[B][6:9] = c[L][6:9]
            c[L][6:9] = t
    elif face == F:
        if direction == 'cw':
            t = [c[U][6], c[U][7], c[U][8]]
            c[U][6], c[U][7], c[U][8] = c[L][8], c[L][5], c[L][2]
            c[L][2], c[L][5], c[L][8] = c[D][0], c[D][1], c[D][2]
            c[D][0], c[D][1], c[D][2] = c[R][6], c[R][3], c[R][0]
            c[R][0], c[R][3], c[R][6] = t
        else:
            t = [c[U][6], c[U][7], c[U][8]]
            c[U][6], c[U][7], c[U][8] = c[R][0], c[R][3], c[R][6]
            c[R][0], c[R][3], c[R][6] = c[D][2], c[D][1], c[D][0]
            c[D][0], c[D][1], c[D][2] = c[L][2], c[L][5], c[L][8]
            c[L][2], c[L][5], c[L][8] = t[2], t[1], t[0]
    elif face == B:
        if direction == 'cw':
            t = [c[U][0], c[U][1], c[U][2]]
            c[U][0], c[U][1], c[U][2] = c[R][2], c[R][5], c[R][8]
            c[R][2], c[R][5], c[R][8] = c[D][8], c[D][7], c[D][6]
            c[D][6], c[D][7], c[D][8] = c[L][0], c[L][3], c[L][6]
            c[L][0], c[L][3], c[L][6] = t[2], t[1], t[0]
        else:
            t = [c[U][0], c[U][1], c[U][2]]
            c[U][0], c[U][1], c[U][2] = c[L][6], c[L][3], c[L][0]
            c[L][0], c[L][3], c[L][6] = c[D][6], c[D][7], c[D][8]
            c[D][6], c[D][7], c[D][8] = c[R][8], c[R][5], c[R][2]
            c[R][2], c[R][5], c[R][8] = t
    elif face == L:
        if direction == 'cw':
            t = [c[U][0], c[U][3], c[U][6]]
            c[U][0], c[U][3], c[U][6] = c[B][8], c[B][5], c[B][2]
            c[B][2], c[B][5], c[B][8] = c[D][0], c[D][3], c[D][6]
            c[D][0], c[D][3], c[D][6] = c[F][0], c[F][3], c[F][6]
            c[F][0], c[F][3], c[F][6] = t
        else:
            t = [c[U][0], c[U][3], c[U][6]]
            c[U][0], c[U][3], c[U][6] = c[F][0], c[F][3], c[F][6]
            c[F][0], c[F][3], c[F][6] = c[D][0], c[D][3], c[D][6]
            c[D][0], c[D][3], c[D][6] = c[B][8], c[B][5], c[B][2]
            c[B][2], c[B][5], c[B][8] = t[2], t[1], t[0]
    elif face == R:
        if direction == 'cw':
            t = [c[U][2], c[U][5], c[U][8]]
            c[U][2], c[U][5], c[U][8] = c[F][2], c[F][5], c[F][8]
            c[F][2], c[F][5], c[F][8] = c[D][2], c[D][5], c[D][8]
            c[D][2], c[D][5], c[D][8] = c[B][6], c[B][3], c[B][0]
            c[B][0], c[B][3], c[B][6] = t[2], t[1], t[0]
        else:
            t = [c[U][2], c[U][5], c[U][8]]
            c[U][2], c[U][5], c[U][8] = c[B][6], c[B][3], c[B][0]
            c[B][0], c[B][3], c[B][6] = c[D][8], c[D][5], c[D][2]
            c[D][2], c[D][5], c[D][8] = c[F][2], c[F][5], c[F][8]
            c[F][2], c[F][5], c[F][8] = t

    return c


class RotateAffordance(Affordance):
    """Single affordance for rotating a face of the cube."""

    def _render_hints(self) -> dict:
        return {"type": "small_button"}


def _render_face(stickers: list[str], label: str) -> str:
    """Render a 3x3 face as an HTML grid."""
    sz = 30
    html = f'<div style="display: inline-grid; grid-template-columns: repeat(3, {sz}px);'
    html += f' grid-template-rows: repeat(3, {sz}px); gap: 1px; margin: 2px;">'
    for s in stickers:
        color = COLORS.get(s, '#999')
        border = '1px solid #333'
        html += f'<div style="background:{color}; border:{border}; width:{sz}px; height:{sz}px;"></div>'
    html += '</div>'
    return html


@dataclass
class RubiksCubeComponent(Component):
    """A fully functional Rubik's Cube — a complex component."""

    @property
    def cube(self) -> dict:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored
        return copy.deepcopy(SOLVED)

    @property
    def is_solved(self) -> bool:
        return self.cube == SOLVED

    @property
    def is_complete(self) -> bool:
        return self.is_solved

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "faces": self.cube,
            "solved": self.is_solved,
        }

    def get_affordances(self) -> list[Affordance]:
        if self.is_solved:
            return [
                SimpleButtonAffordance(
                    label="Shuffle",
                    method="POST",
                    url=self.url,
                    body={"action": "shuffle"},
                    instruction="Shuffle the cube to begin.",
                ),
            ]
        return [
            RotateAffordance(
                label="Rotate",
                method="POST",
                url=self.url,
                body={"action": "rotate", "face": "<U|D|L|R|F|B>", "direction": "<cw|ccw>"},
                instruction="Rotate a face. U=Up, D=Down, L=Left, R=Right, F=Front, B=Back. cw=clockwise, ccw=counter-clockwise.",
            ),
            SimpleButtonAffordance(
                label="Shuffle",
                method="POST",
                url=self.url,
                body={"action": "shuffle"},
                instruction="Randomly shuffle the cube with 20 random rotations.",
            ),
            SimpleButtonAffordance(
                label="Restart",
                method="POST",
                url=self.url,
                body={"action": "restart"},
                instruction="Reset the cube to its solved state.",
            ),
        ]

    def render_from_data(self, data: dict) -> str:
        faces = data.get("faces", {})
        solved = data.get("solved", False)
        sz = 30
        gap = 1
        face_w = sz * 3 + gap * 2 + 4
        face_html = {fk: _render_face(faces.get(fk, []), fk) for fk in [U, D, L, R, F, B]}
        return render_template("rubikscube.html", data=data, ef=self, faces=faces, solved=solved, face_w=face_w, face_html=face_html, url=self.url)

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "rotate")
        if action == "rotate":
            face = body.get("face", "")
            direction = body.get("direction", "cw")
            if face in (U, D, L, R, F, B) and direction in ("cw", "ccw"):
                new_cube = _apply_rotation(self.cube, face, direction)
                self._store.set(self._scope, self.key, new_cube)
        elif action == "shuffle":
            cube = copy.deepcopy(SOLVED)
            faces = [U, D, L, R, F, B]
            directions = ["cw", "ccw"]
            for _ in range(20):
                cube = _apply_rotation(cube, random.choice(faces), random.choice(directions))
            self._store.set(self._scope, self.key, cube)
        elif action == "restart":
            self._store.set(self._scope, self.key, copy.deepcopy(SOLVED))
        return self.serialize()
