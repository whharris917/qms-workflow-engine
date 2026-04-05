"""HistoryForm — wraps an eigenform and keeps an append-only history of all changes.

Every time the wrapped eigenform's state changes, a timestamped snapshot
is appended to the history. The history is never editable — no delete, no
modify, no reorder. Append-only.

Browsing: affordances let the user view previous versions read-only.
The current version is always the live, interactive eigenform.

Change detection is lazy: on every serialize(), the child's current state
is compared against the last recorded snapshot. If different, a new entry
is appended. Since every POST triggers a page serialize (via the route
handler), every mutation is captured.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.eigenform import Eigenform
from engine.templates import render_template
from engine.store import Store


@dataclass
class HistoryForm(Eigenform):
    """Wraps an eigenform with append-only change history."""
    eigenform: Eigenform = None

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        if self.eigenform:
            desc["eigenform"] = self.eigenform.to_descriptor()
        return desc

    @property
    def children(self) -> list[Eigenform]:
        return [self.eigenform] if self.eigenform else []

    @property
    def is_complete(self) -> bool:
        if self.eigenform is None:
            return True
        return self.eigenform.is_complete

    @property
    def has_data(self) -> bool:
        if self.eigenform is None:
            return False
        return self.eigenform.has_data

    def _bind_children(self, store: Store, url_prefix: str):
        if self.eigenform is not None:
            self.eigenform = self.eigenform.bind(
                store=store, scope=self._scope,
                url_prefix=f"{url_prefix}/{self.key}",
            )

    # --- History storage (append-only) ---

    @property
    def _history(self) -> list[dict]:
        """The append-only history list from the store."""
        return self._store.get(self._scope, f"{self.key}.__history") or []

    def _child_snapshot(self) -> dict:
        """Capture the child's state for comparison, without affordances."""
        state = self.eigenform.serialize()
        if state:
            state.pop("affordances", None)
        return state

    def _maybe_record(self):
        """Compare child state to last snapshot; append if changed."""
        if self.eigenform is None or self._store is None:
            return
        current = self._child_snapshot()
        history = self._history
        last_snapshot = history[-1]["snapshot"] if history else None
        if current != last_snapshot:
            history.append({
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "snapshot": current,
            })
            self._store.set(self._scope, f"{self.key}.__history", history)

    # --- Viewing state ---

    @property
    def _viewing_version(self) -> int | None:
        """Which historical version is being viewed (None = current live)."""
        val = self._store.get(self._scope, f"{self.key}.__viewing")
        if val is not None:
            history = self._history
            if 0 <= val < len(history):
                return val
        return None

    # --- Serialization ---

    def _serialize_state(self) -> dict:
        self._maybe_record()
        history = self._history
        viewing = self._viewing_version
        return self._base_state() | {
            "history_length": len(history),
            "viewing_version": viewing,
        }

    def _serialize_full(self) -> dict:
        state = self._serialize_state()
        history = self._history
        viewing = self._viewing_version

        if viewing is not None:
            entry = history[viewing]
            state["eigenform"] = entry["snapshot"]
            state["viewing_timestamp"] = entry["timestamp"]
            state["read_only"] = True
        else:
            state["eigenform"] = self.eigenform.serialize() if self.eigenform else None
            state["read_only"] = False

        state["complete"] = self.is_complete

        # Timeline: compact summary of all history entries
        state["timeline"] = [
            {"version": i, "timestamp": h["timestamp"]}
            for i, h in enumerate(history)
        ]

        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def get_affordances(self) -> list[Affordance]:
        affordances: list[Affordance] = []
        history = self._history
        viewing = self._viewing_version

        if viewing is not None:
            # Viewing history — offer navigation and return
            affordances.append(SimpleButtonAffordance(
                label="Back to Current",
                method="POST",
                url=self.url,
                body={"action": "view_current"},
                instruction="Return to the live, editable version.",
            ))
            if viewing > 0:
                affordances.append(SimpleButtonAffordance(
                    label="\u2190 Older",
                    method="POST",
                    url=self.url,
                    body={"action": "view_version", "version": viewing - 1},
                    instruction=f"View version {viewing - 1}.",
                ))
            if viewing < len(history) - 1:
                affordances.append(SimpleButtonAffordance(
                    label="Newer \u2192",
                    method="POST",
                    url=self.url,
                    body={"action": "view_version", "version": viewing + 1},
                    instruction=f"View version {viewing + 1}.",
                ))
        elif history:
            # Viewing current — offer to browse history
            affordances.append(SimpleButtonAffordance(
                label=f"View History ({len(history)} versions)",
                method="POST",
                url=self.url,
                body={"action": "view_version", "version": len(history) - 1},
                instruction="View the most recent historical snapshot.",
            ))

        return affordances

    # --- Rendering ---

    def render_from_data(self, data: dict) -> str:
        viewing = data.get("viewing_version")
        read_only = data.get("read_only", False)
        timeline = data.get("timeline", [])
        child_html = None
        snapshot_html = ""
        if read_only:
            snapshot = data.get("eigenform", {})
            if snapshot:
                snapshot_html = self._render_snapshot(snapshot)
        else:
            if self.eigenform:
                child_html = self.eigenform.render()
        return render_template("history.html", data=data, ef=self, child_html=child_html, viewing=viewing, read_only=read_only, timeline=timeline, viewing_ts=data.get("viewing_timestamp", ""), snapshot_html=snapshot_html)

    @staticmethod
    def _render_snapshot(snapshot: dict) -> str:
        from markupsafe import escape
        html = ""
        label = snapshot.get("label", "")
        if label:
            html += f'<div style="font-weight: 600; margin-bottom: 4px;">{escape(label)}</div>'
        skip = {"label", "instruction", "complete", "edit_mode"}
        for k, v in snapshot.items():
            if k in skip or v is None:
                continue
            if isinstance(v, (list, dict)) and not v:
                continue
            html += f'<div style="font-size: 13px; margin: 2px 0;"><span style="color: #888;">{escape(k)}:</span> <span style="color: #333;">{escape(str(v))}</span></div>'
        return html

    # --- Action handling ---

    def _handle(self, body: dict) -> dict:
        action = body.get("action", "")
        if action == "view_version":
            version = body.get("version")
            if isinstance(version, int):
                history = self._history
                if 0 <= version < len(history):
                    self._store.set(self._scope, f"{self.key}.__viewing", version)
            return self.serialize()
        if action == "view_current":
            self._store.delete(self._scope, f"{self.key}.__viewing")
            return self.serialize()
        # Delegate unknown actions to child
        if self.eigenform:
            return self.eigenform.handle(body)
        return self.serialize()

    def _clear_data(self):
        """Clear the child's data and viewing state. History is NEVER cleared."""
        if self.eigenform:
            self.eigenform._clear_data()
        if self._store:
            self._store.delete(self._scope, f"{self.key}.__viewing")
