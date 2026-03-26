"""JSON file store for eigenform state."""

from __future__ import annotations

import json
from pathlib import Path


class Store:
    """Persists eigenform values as a JSON file on disk, scoped by resource."""

    def __init__(self, path: Path):
        self.path = path
        self._data: dict = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text())

    def get(self, scope: str, key: str):
        return self._data.get(scope, {}).get(key)

    def set(self, scope: str, key: str, value):
        if scope not in self._data:
            self._data[scope] = {}
        self._data[scope][key] = value
        self._save()

    def clear_scope(self, scope: str):
        """Remove all data for a scope."""
        if scope in self._data:
            del self._data[scope]
            self._save()

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))
