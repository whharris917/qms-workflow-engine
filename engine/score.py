"""Score — a read-only component that grades sibling components against an answer key.

Reads sibling values from the shared store/scope. Computes results
live on every serialize/render — no grading action needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.component import Component
from engine.sibling_ref import SiblingRef
from engine.templates import render_template


@dataclass
class Score(Component):
    """Grades sibling components by comparing stored values to an answer key.

    answer_key maps sibling component keys to their expected values:
      - str: exact match (for TextForm, ChoiceForm)
      - dict[str, bool]: exact match on checked items (for CheckboxForm)
      - callable: receives the stored value, returns bool
    """
    form = "score"

    answer_key: dict[str, Any] = field(default_factory=dict)

    def _sibling_refs(self) -> list[SiblingRef]:
        # Keys in answer_key are implicit sibling references.
        return [SiblingRef(k) for k in self.answer_key.keys()]

    @property
    def is_complete(self) -> bool:
        return True

    def _grade(self) -> list[dict]:
        """Grade each question. Returns list of {key, answer, expected, correct, answered}."""
        results = []
        for qkey, expected in self.answer_key.items():
            stored = self._store.get(self._scope, qkey) if self._store else None
            answered = stored is not None
            if callable(expected):
                correct = expected(stored) if answered else False
            elif isinstance(expected, dict):
                correct = stored == expected if answered else False
            else:
                if isinstance(stored, str) and isinstance(expected, str):
                    correct = stored.strip().lower() == expected.strip().lower()
                else:
                    correct = stored == expected
            results.append({
                "key": qkey,
                "answer": stored,
                "expected": expected if not callable(expected) else "(custom)",
                "correct": correct,
                "answered": answered,
            })
        return results

    def _serialize_state(self) -> dict:
        results = self._grade()
        total = len(results)
        answered = sum(1 for r in results if r["answered"])
        correct = sum(1 for r in results if r["correct"])
        pct = round(100 * correct / total) if total and answered == total else None
        return self._base_state() | {
            "depends_on": list(self.answer_key.keys()),
            "total": total,
            "answered": answered,
            "correct": correct,
            "percent": pct,
            "results": results,
        }

    def render_from_data(self, data: dict) -> str:
        return render_template("score.html", data=data, ef=self,
                               url_prefix=self._url_prefix,
                               format_answer=_format_answer)

    def get_affordances(self):
        return []

    def _handle(self, body: dict) -> dict:
        return self.serialize()


def _format_answer(val) -> str:
    from markupsafe import escape as _esc
    if val is None:
        return '<span style="color: #888;">--</span>'
    if isinstance(val, dict):
        selected = [k for k, v in val.items() if v and not k.startswith("__")]
        return str(_esc(", ".join(selected))) if selected else '<span style="color: #888;">none</span>'
    return str(_esc(str(val)))
