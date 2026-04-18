"""Component construction helpers.

These are small factories and compute-function builders that sit on top of the
core component classes. They are not a taxonomy entry — they just reduce
boilerplate for common patterns (grading sibling answers, deriving values).
"""

from __future__ import annotations

from typing import Any, Callable

from engine.computation import Computation


def grade(answer_key: dict[str, Any]) -> Callable[[dict], dict]:
    """Build a Computation compute_fn that grades sibling answers against a key.

    Semantics match the former Score component:

    - callable expected values receive the stored value and return bool
    - dict expected values (for CheckboxForm state) require exact equality
    - string expected values use case-insensitive, stripped comparison
    - any other type uses `==`

    The returned compute_fn reads from the `siblings` dict that Computation
    passes in, and returns a grading summary shaped for computed.html:
    a `message` with the running total/percent, plus one row per question
    with a pass/fail/unanswered marker.
    """
    def _compute(siblings: dict) -> dict:
        total = len(answer_key)
        correct = 0
        answered = 0
        rows: dict[str, str] = {}

        for qkey, expected in answer_key.items():
            stored = siblings.get(qkey)
            is_answered = stored is not None
            if is_answered:
                answered += 1

            if callable(expected):
                ok = expected(stored) if is_answered else False
            elif isinstance(expected, dict):
                ok = (stored == expected) if is_answered else False
            elif isinstance(stored, str) and isinstance(expected, str):
                ok = stored.strip().lower() == expected.strip().lower()
            else:
                ok = (stored == expected)

            if ok:
                correct += 1

            if not is_answered:
                rows[qkey] = "\u2014 not answered"
            elif ok:
                rows[qkey] = "\u2713 correct"
            else:
                shown = "(custom)" if callable(expected) else expected
                rows[qkey] = f"\u2717 expected {shown!r}"

        if answered < total:
            message = f"{answered}/{total} answered."
        else:
            pct = round(100 * correct / total) if total else 0
            message = f"Score: {correct}/{total} ({pct}%)"

        return {"message": message, **rows}

    return _compute


def graded(answer_key: dict[str, Any], **kwargs: Any) -> Computation:
    """Build a Computation that grades its siblings against `answer_key`.

    A one-liner replacement for the former Score component. `depends_on` is
    derived from the answer_key's keys; any other Computation field
    (`key`, `label`, `instruction`, `display_format`, `store_result`) can
    be passed as a keyword argument.

    Example::

        graded(
            {"q1": "Paris", "q2": "Rome"},
            key="geo-score", label="Results",
            instruction="Grades your answers.",
        )
    """
    return Computation(
        depends_on=list(answer_key.keys()),
        compute_fn=grade(answer_key),
        **kwargs,
    )
