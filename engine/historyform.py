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
from html import escape
from typing import Any

from engine.affordances import Affordance, SimpleButtonAffordance, SwitchTabAffordance
from engine.bases import WrapperForm
from engine.eigenform import Eigenform
from engine.store import Store


@dataclass
class HistoryForm(WrapperForm):
    """Wraps an eigenform with append-only change history."""
    eigenform: Eigenform = None

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        if self.eigenform:
            desc["eigenform"] = self.eigenform.to_descriptor()
        return desc

    @property
    def _wrapped_child(self) -> Eigenform | None:
        return self.eigenform

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
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'

        viewing = data.get("viewing_version")
        read_only = data.get("read_only", False)
        timeline = data.get("timeline", [])
        affs = data.get("affordances", [])

        # Timeline bar
        if timeline:
            history_len = len(timeline)
            html += '<div style="margin-bottom: 12px;">'
            html += (
                f'<div style="font-size: 11px; color: #888; margin-bottom: 6px;">'
                f'{history_len} version{"s" if history_len != 1 else ""} recorded</div>'
            )
            html += '<div style="display: flex; align-items: center; gap: 3px; flex-wrap: wrap;">'
            for entry in timeline:
                v = entry["version"]
                is_viewing = v == viewing
                is_latest = v == history_len - 1
                if is_viewing:
                    style = (
                        "width: 10px; height: 10px; border-radius: 50%;"
                        " background: #6c5ce7; border: 2px solid #6c5ce7;"
                    )
                elif is_latest and viewing is None:
                    style = (
                        "width: 10px; height: 10px; border-radius: 50%;"
                        " background: #2a2; border: 2px solid #2a2;"
                    )
                else:
                    style = (
                        "width: 8px; height: 8px; border-radius: 50%;"
                        " background: #ddd; border: 2px solid #ddd;"
                    )
                ts = entry["timestamp"]
                # Show just time portion for compact display
                time_display = ts.split("T")[1] if "T" in ts else ts
                html += f'<span style="{style}" title="v{v}: {escape(ts)}"></span>'
            html += '</div>'
            html += '</div>'

        if read_only:
            # Historical view — render snapshot as read-only
            ts = data.get("viewing_timestamp", "")
            html += (
                f'<div style="background: #f8f0ff; border: 1px solid #d4b8e8;'
                f' border-radius: 8px; padding: 12px; margin-bottom: 8px;">'
                f'<div style="font-size: 11px; color: #7b2d8b; margin-bottom: 8px;'
                f' font-weight: 600;">HISTORICAL VERSION {viewing} &mdash; {escape(ts)}'
                f' &mdash; READ ONLY</div>'
            )
            snapshot = data.get("eigenform", {})
            if snapshot:
                html += self._render_snapshot(snapshot)
            html += '</div>'

            # Navigation
            for aff in affs:
                html += render_affordance_html(aff)
        else:
            # Current live view — render the actual eigenform
            if self.eigenform:
                html += self.eigenform.render()

            # History affordance (view history button)
            for aff in affs:
                html += render_affordance_html(aff)

        return html

    @staticmethod
    def _render_snapshot(snapshot: dict) -> str:
        """Render a historical snapshot as a read-only display."""
        html = ''
        label = snapshot.get("label", "")
        if label:
            html += f'<div style="font-weight: 600; margin-bottom: 4px;">{escape(label)}</div>'

        # Show key-value pairs from the snapshot, skipping metadata
        skip = {"label", "instruction", "complete", "edit_mode"}
        for k, v in snapshot.items():
            if k in skip:
                continue
            if v is None:
                continue
            if isinstance(v, list) and not v:
                continue
            if isinstance(v, dict) and not v:
                continue
            html += (
                f'<div style="font-size: 13px; margin: 2px 0;">'
                f'<span style="color: #888;">{escape(k)}:</span> '
                f'<span style="color: #333;">{escape(str(v))}</span>'
                f'</div>'
            )
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
