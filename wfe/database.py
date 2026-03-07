"""Mock database for workflow engine external state.

Provides a simple key-value store backed by a JSON file.
Hooks read from and write to this database to simulate
external state (document approval status, versions, etc.).

This is a seam: when integrating with the real QMS, only
the hook implementations change — not the engine or workflows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DB_PATH = Path("db.json")


class MockDatabase:
    """Key-value store backed by a JSON file."""

    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self._data: dict = {}
        if self.path.exists():
            self._data = json.loads(self.path.read_text())

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._flush()

    def delete(self, key: str) -> None:
        self._data.pop(key, None)
        self._flush()

    def list_keys(self) -> list[str]:
        return list(self._data.keys())

    def _flush(self) -> None:
        self.path.write_text(json.dumps(self._data, indent=2))
