"""JSON file store for eigenform state."""

from __future__ import annotations

import json
from pathlib import Path


class Store:
    """Persists eigenform values as a JSON file on disk, scoped by resource.

    The store tracks the file's modification time and re-reads from disk
    whenever the file has changed or been deleted externally. This ensures
    the in-memory cache always reflects the underlying file.
    """

    def __init__(self, path: Path):
        self.path = path
        self._data: dict = {}
        self._mtime: float | None = None
        self._load()

    def _load(self):
        """Read data from disk and record the file's mtime.

        An empty file is treated as {} — this can arise from an
        interrupted write, and failing to parse would wedge the page.
        """
        if self.path.exists():
            text = self.path.read_text()
            self._data = json.loads(text) if text.strip() else {}
            self._mtime = self.path.stat().st_mtime
        else:
            self._data = {}
            self._mtime = None

    def _sync(self):
        """Re-read from disk if the file has changed or been deleted."""
        if self.path.exists():
            current_mtime = self.path.stat().st_mtime
            if current_mtime != self._mtime:
                self._load()
        elif self._mtime is not None:
            # File was deleted externally
            self._data = {}
            self._mtime = None

    def get(self, scope: str, key: str):
        self._sync()
        return self._data.get(scope, {}).get(key)

    def set(self, scope: str, key: str, value):
        self._sync()
        if scope not in self._data:
            self._data[scope] = {}
        self._data[scope][key] = value
        self._save()

    def delete(self, scope: str, key: str):
        """Remove a single key from a scope."""
        self._sync()
        if scope in self._data and key in self._data[scope]:
            del self._data[scope][key]
            self._save()

    def clear_scope(self, scope: str):
        """Remove all data for a scope."""
        self._sync()
        if scope in self._data:
            del self._data[scope]
            self._save()

    def snapshot_scope(self, scope: str) -> dict:
        """Return a deep copy of all data for a scope."""
        import copy
        self._sync()
        return copy.deepcopy(self._data.get(scope, {}))

    def restore_scope(self, scope: str, data: dict):
        """Replace all data for a scope with a deep copy of the given data."""
        import copy
        self._sync()
        self._data[scope] = copy.deepcopy(data)
        self._save()

    def _save(self):
        # Atomic write: temp file + rename. Prevents 0-byte files when
        # the process is killed mid-write (e.g., Flask auto-reload).
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.parent / (self.path.name + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self.path)
        self._mtime = self.path.stat().st_mtime
