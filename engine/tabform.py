"""TabForm — an eigenform that shows one tab at a time."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance, SwitchTabAffordance
from engine.eigenform import Eigenform
from engine.store import Store


@dataclass
class TabForm(Eigenform):
    """An eigenform with multiple tabs. Only the active tab is visible.

    The active tab is persisted state. Switching tabs is an affordance.
    Both the agent and human see only the active tab's eigenforms —
    faithful projection requires that hidden tabs are absent from
    the serialization.
    """
    tabs: dict[str, Eigenform] = field(default_factory=dict)  # {tab_key: eigenform}

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["tabs"] = {k: v.to_descriptor() for k, v in self.tabs.items()}
        return desc

    @property
    def children(self) -> list[Eigenform]:
        return list(self.tabs.values())

    @property
    def active_tab_key(self) -> str:
        """The currently active tab key, from the store."""
        stored = self.value
        if stored and stored in self.tabs:
            return stored
        return next(iter(self.tabs)) if self.tabs else ""

    @property
    def active_tab(self) -> Eigenform | None:
        return self.tabs.get(self.active_tab_key)

    def _bind_children(self, store: Store, url_prefix: str):
        self.tabs = {
            tab_key: ef.bind(store=store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
            for tab_key, ef in self.tabs.items()
        }

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "active_tab": self.active_tab_key,
            "tab_keys": list(self.tabs.keys()),
        }

    def _serialize_full(self) -> dict:
        state = self._serialize_state()
        active = self.active_tab
        state["eigenform"] = active.serialize() if active else None
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.tabs.values())

    def get_affordances(self) -> list[Affordance]:
        affordances: list[Affordance] = []
        for tab_key, ef in self.tabs.items():
            if tab_key != self.active_tab_key:
                affordances.append(SwitchTabAffordance(
                    label=ef.label,
                    method="POST",
                    url=f"{self._url_prefix}/{self.key}",
                    body={"tab": tab_key},
                    instruction=f"Switch to the {ef.label} tab.",
                ))
        return affordances

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        # Tab bar — active tab shown as bold label, inactive tabs as affordance buttons
        active_key = data.get("active_tab", "")
        affs = data.get("affordances", [])
        html += '<div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px;">'
        for tab_key in data.get("tab_keys", []):
            if tab_key == active_key:
                # Get the label from the active tab eigenform
                tab_ef = self.tabs.get(tab_key)
                label = tab_ef.label if tab_ef else tab_key
                html += (
                    f'<span style="font-weight: bold;'
                    f' padding: 2px 8px; border-bottom: 2px solid #333;">'
                    f'{escape(label)}</span>'
                )
            else:
                for aff in affs:
                    if aff.get("body", {}).get("tab") == tab_key:
                        html += render_affordance_html(aff)
                        break
        html += '</div>'
        # Active tab content
        active = self.active_tab
        if active:
            html += active.render()
        return html

    def _handle(self, body: dict) -> dict:
        """Handle tab switch."""
        tab_key = body.get("tab")
        if tab_key and tab_key in self.tabs:
            self._store.set(self._scope, self.key, tab_key)
        return self.serialize()

    def handle_action(self, key: str, body: dict) -> bool:
        """Route action: tab switch goes to self, otherwise to active tab.
        Returns True if the action was handled."""
        if key == self.key:
            self.handle(body)
            return True
        active = self.active_tab
        if active and active.key == key:
            active.handle(body)
            return True
        return False
