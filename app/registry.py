"""Instance registry — tracks spawned page instances in a JSON file."""

from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path


class InstanceRegistry:
    """Manages page instances in a JSON file.

    Follows the same mtime-based sync pattern as Store — re-reads
    from disk when the file has changed externally.
    """

    def __init__(self, data_dir: Path):
        self.path = data_dir / "instances.json"
        self._data: dict = {"_counters": {}, "instances": {}}
        self._mtime: float | None = None
        self._load()

    def _load(self):
        if self.path.exists():
            text = self.path.read_text()
            self._data = json.loads(text) if text.strip() else {"_counters": {}, "instances": {}}
            self._mtime = self.path.stat().st_mtime
        else:
            self._data = {"_counters": {}, "instances": {}}
            self._mtime = None

    def _sync(self):
        if self.path.exists():
            current_mtime = self.path.stat().st_mtime
            if current_mtime != self._mtime:
                self._load()
        elif self._mtime is not None:
            self._data = {"_counters": {}, "instances": {}}
            self._mtime = None

    def _save(self):
        # Atomic write: temp file + rename. Prevents 0-byte files when
        # the process is killed mid-write (e.g., Flask auto-reload).
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.parent / (self.path.name + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.replace(self.path)
        self._mtime = self.path.stat().st_mtime

    def list_instances(self) -> dict[str, dict]:
        self._sync()
        return dict(self._data.get("instances", {}))

    def get_instance(self, instance_id: str) -> dict | None:
        self._sync()
        return self._data.get("instances", {}).get(instance_id)

    def create_instance(self, type_key: str, label: str,
                        force_id: str | None = None) -> str:
        self._sync()
        instances = self._data.setdefault("instances", {})

        if force_id is not None:
            instance_id = force_id
        else:
            instance_id = uuid.uuid4().hex[:8]

        instances[instance_id] = {
            "type": type_key,
            "label": label,
            "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        self._save()
        return instance_id

    def delete_instance(self, instance_id: str, data_dir: Path) -> bool:
        self._sync()
        instances = self._data.get("instances", {})
        if instance_id not in instances:
            return False
        del instances[instance_id]
        self._save()
        # Remove the instance's data file
        data_file = data_dir / f"{instance_id}.json"
        if data_file.exists():
            data_file.unlink()
        return True
