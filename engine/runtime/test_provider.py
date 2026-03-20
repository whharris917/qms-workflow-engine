"""In-memory counter provider for testing the external state framework.

Registered at startup to exercise all four provider protocol methods:
query, get_affordances, execute, evaluate.
"""

from __future__ import annotations

from typing import Any


class CounterProvider:
    """A trivial provider that maintains an in-memory counter."""

    provider_id = "counter"

    def __init__(self):
        self._counters: dict[str, int] = {}

    def _key(self, bindings: dict) -> str:
        return bindings.get("counter_id", "default")

    def query(self, bindings: dict[str, Any]) -> dict[str, Any]:
        key = self._key(bindings)
        return {"counter": self._counters.get(key, 0)}

    def get_affordances(self, bindings: dict[str, Any], state: dict[str, Any],
                        api_base: str) -> list[dict]:
        return [{
            "label": f"Increment counter (current: {state.get('counter', 0)})",
            "method": "POST",
            "url": f"{api_base}/ext.counter.increment",
            "body": {},
        }]

    def execute(self, bindings: dict[str, Any], action: str,
                params: dict[str, Any]) -> dict[str, Any]:
        key = self._key(bindings)
        if action == "increment":
            self._counters[key] = self._counters.get(key, 0) + 1
            return {"ok": True, "counter": self._counters[key]}
        if action == "reset":
            self._counters[key] = 0
            return {"ok": True, "counter": 0}
        return {"ok": False, "error": f"Unknown action: {action}"}

    def evaluate(self, bindings: dict[str, Any], state: dict[str, Any],
                 condition: dict) -> tuple[bool, str]:
        ctype = condition.get("type", "")
        if ctype == "counter_above":
            threshold = condition.get("value", 0)
            actual = state.get("counter", 0)
            passed = actual > threshold
            return passed, f"counter={actual} > {threshold}: {passed}"
        if ctype == "counter_equals":
            expected = condition.get("value", 0)
            actual = state.get("counter", 0)
            passed = actual == expected
            return passed, f"counter={actual} == {expected}: {passed}"
        return False, f"Unknown counter condition: {ctype}"
