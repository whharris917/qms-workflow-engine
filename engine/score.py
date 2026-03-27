"""ScoreForm — a read-only eigenform that grades sibling eigenforms against an answer key.

Reads sibling values from the shared store/scope. Computes results
live on every serialize/render — no grading action needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.eigenforms import Eigenform


@dataclass
class ScoreForm(Eigenform):
    """Grades sibling eigenforms by comparing stored values to an answer key.

    answer_key maps sibling eigenform keys to their expected values:
      - str: exact match (for TextForm, ChoiceForm)
      - dict[str, bool]: exact match on checked items (for CheckboxForm)
      - callable: receives the stored value, returns bool
    """
    answer_key: dict[str, Any] = field(default_factory=dict)

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
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "total": total,
            "answered": answered,
            "correct": correct,
            "percent": pct,
            "results": results,
        }

    def render_from_data(self, data: dict) -> str:
        total = data["total"]
        answered = data["answered"]
        correct = data["correct"]

        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        if answered < total:
            html += f'<p><strong>{answered}/{total}</strong> questions answered.</p>'
        else:
            html += f'<p><strong>Score: {correct}/{total} ({data["percent"]}%)</strong></p>'

        html += '<table style="border-collapse: collapse; width: 100%;">'
        html += ('<tr><th style="text-align: left; padding: 4px; border-bottom: 1px solid #ccc;">Q</th>'
                 '<th style="text-align: left; padding: 4px; border-bottom: 1px solid #ccc;">Your Answer</th>'
                 '<th style="text-align: left; padding: 4px; border-bottom: 1px solid #ccc;">Result</th></tr>')

        for r in data["results"]:
            answer_display = _format_answer(r["answer"])
            if not r["answered"]:
                result = '<span style="color: #888;">--</span>'
            elif r["correct"]:
                result = '<span style="color: #2a2;">Correct</span>'
            else:
                expected_display = _format_answer(r["expected"])
                result = f'<span style="color: #c22;">Incorrect</span> <span style="color: #888; font-size: 0.9em;">(expected: {expected_display})</span>'
            html += (f'<tr><td style="padding: 4px; border-bottom: 1px solid #eee;">{escape(r["key"])}</td>'
                     f'<td style="padding: 4px; border-bottom: 1px solid #eee;">{answer_display}</td>'
                     f'<td style="padding: 4px; border-bottom: 1px solid #eee;">{result}</td></tr>')

        html += '</table>'
        return html

    def get_affordances(self):
        return []

    def _handle(self, body: dict) -> dict:
        return self.serialize()


def _format_answer(val) -> str:
    if val is None:
        return '<span style="color: #888;">--</span>'
    if isinstance(val, dict):
        selected = [k for k, v in val.items() if v and not k.startswith("__")]
        return escape(", ".join(selected)) if selected else '<span style="color: #888;">none</span>'
    return escape(str(val))
