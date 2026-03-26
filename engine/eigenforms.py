"""Eigenform — the self-contained unit of workflow interaction.

An eigenform has internal state, serializes itself to JSON, renders
HTML from that JSON, and exposes affordances as POSTable actions.
Each eigenform is a HATEOAS-compliant mini-application.

render() calls serialize() first, then render_from_data(data) produces
HTML purely from the serialized dict. This guarantees HTML and JSON
cannot diverge. Affordances are pure data — the eigenform is responsible
for accounting for each one in render_from_data().

Once bound to a store, scope, and url_prefix, an eigenform is fully
self-sufficient — it can serialize, render, and handle actions
without any external input.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance, CheckboxAffordance, SetValueAffordance, SimpleButtonAffordance
from engine.store import Store


@dataclass
class Eigenform:
    """Base protocol for all eigenform types."""
    key: str
    label: str
    instruction: str | None = None

    # Binding — set via bind(), not at construction
    _store: Store | None = None
    _scope: str | None = None
    _url_prefix: str | None = None

    @property
    def children(self) -> list[Eigenform]:
        """Direct child eigenforms. Containers override this."""
        return []

    def _bind_children(self, store: Store, url_prefix: str):
        """Bind all children. Containers with non-standard child storage override this."""
        pass

    def bind(self, store: Store, scope: str, url_prefix: str) -> Eigenform:
        """Produce a bound copy of this eigenform. The original is unchanged.

        Containers that hold children should override _bind_children()
        rather than bind() itself, unless they need custom bind logic
        (e.g., PageForm creates its own Store).
        """
        bound = copy.deepcopy(self)
        bound._store = store
        bound._scope = scope
        bound._url_prefix = url_prefix
        bound._bind_children(store, url_prefix)
        return bound

    @property
    def value(self) -> Any:
        """The current value, fetched from the store."""
        if self._store is None:
            return None
        return self._store.get(self._scope, self.key)

    @property
    def is_complete(self) -> bool:
        """Whether this eigenform has been completed. Subclasses must implement."""
        raise NotImplementedError

    @property
    def url(self) -> str:
        """The URL for this eigenform's actions."""
        return f"{self._url_prefix}/{self.key}"

    @property
    def uid(self) -> str:
        """Unique DOM ID for this eigenform, scoped to avoid collisions."""
        return f"ef-{self._scope}-{self.key}" if self._scope else f"ef-{self.key}"

    @property
    def form(self) -> str:
        """The eigenform's type name, derived from the class."""
        name = type(self).__name__
        return name.removesuffix("Form").lower()

    def _serialize_state(self) -> dict:
        """Serialize this eigenform's state fields. Subclasses implement this."""
        raise NotImplementedError

    def get_affordances(self) -> list[Affordance]:
        """Produce the affordances available on this eigenform."""
        return []

    def serialize(self) -> dict:
        """Produce the complete canonical representation: state + affordances."""
        state = self._serialize_state()
        state["complete"] = self.is_complete
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def render_from_data(self, data: dict) -> str:
        """Render HTML from the canonical serialized dict.

        Subclasses override this. Every affordance in data["affordances"]
        must be accounted for — either by calling render_affordance_html()
        (which marks it automatically) or by calling mark_rendered() after
        handling it with custom HTML. Unaccounted affordances raise a
        RuntimeError after this method returns.
        """
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data.get("label", ""))}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    @staticmethod
    def mark_rendered(aff: dict):
        """Mark an affordance dict as accounted for (rendered or intentionally skipped)."""
        aff["_rendered"] = True

    def render(self) -> str:
        """Render this eigenform as HTML, wrapped in a standard container.

        Calls serialize() first, then render_from_data() on the result.
        This guarantees HTML and JSON cannot diverge — both derive from
        the same serialized dict. After rendering, checks that all
        affordances were accounted for.
        """
        data = self.serialize()
        for aff in data.get("affordances", []):
            aff["_rendered"] = False
        inner = self.render_from_data(data)

        unrendered = [a for a in data.get("affordances", []) if not a.get("_rendered")]
        if unrendered:
            labels = [a.get("label", "?") for a in unrendered]
            raise RuntimeError(
                f"{type(self).__name__}(key={self.key!r}) did not render "
                f"{len(unrendered)} affordance(s): {labels}. "
                f"Use render_affordance_html() to render or Eigenform.mark_rendered() to skip."
            )

        json_str = escape(json.dumps(data, indent=2))
        uid = self.uid

        complete_color = '#2a2' if self.is_complete else '#888'

        return (
            f'<div class="eigenform" data-form="{self.form}" data-key="{self.key}"'
            f' style="border: 2px solid {complete_color}; padding: 30px 12px 12px 12px; margin: 8px 0; position: relative;">'
            f'<button onclick="var h=document.getElementById(\'{uid}-human\'),j=document.getElementById(\'{uid}-json\'),'
            f'v=j.style.display===\'none\';j.style.display=v?\'block\':\'none\';h.style.display=v?\'none\':\'block\';'
            f'this.textContent=v?\'See HTML\':\'See JSON\'"'
            f' style="position: absolute; top: 8px; right: 8px; font-size: 12px; cursor: pointer; background: #7b2d8b; color: white; border: none; padding: 2px 8px; border-radius: 3px;">See JSON</button>'
            f'<div id="{uid}-human">{inner}</div>'
            f'<pre id="{uid}-json" style="display: none; margin: 0; white-space: pre-wrap;">{json_str}</pre>'
            f'</div>'
        )

    def handle(self, body: dict) -> dict:
        """Handle a POST action. Persists to store, returns serialized state.

        If body contains {"action": "batch", "actions": [...]}, each
        action is executed in sequence. The response is the final
        serialized state. If any action produces an error, execution
        stops and the error is returned.
        """
        if body.get("action") == "batch":
            actions = body.get("actions", [])
            result = self.serialize()
            for action_body in actions:
                result = self.handle(action_body)
                if "error" in result:
                    return result
            return result
        return self._handle(body)

    def _handle(self, body: dict) -> dict:
        """Handle a single action. Subclasses must implement."""
        raise NotImplementedError


@dataclass
class TextForm(Eigenform):
    """Single free-form string input."""
    default: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.value is not None

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "value": self.value if self.value is not None else self.default,
        }

    def render_from_data(self, data: dict) -> str:
        from engine.affordances import render_affordance_html
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        html += f'<p><strong>Value:</strong> {escape(str(data["value"]))}</p>'
        for aff in data.get("affordances", []):
            html += render_affordance_html(aff)
        return html

    def get_affordances(self) -> list[Affordance]:
        return [
            SetValueAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": "<value>"},
                instruction=f"Replace <value> with the desired {self.label.lower()}.",
            )
        ]

    def _handle(self, body: dict) -> dict:
        self._store.set(self._scope, self.key, body.get("value"))
        return self.serialize()


@dataclass
class CheckboxForm(Eigenform):
    """Multi-select: a set of items, each independently selectable.

    Incomplete until at least one item is checked. Include an "N/A" item
    if it's valid for none of the others to apply.
    """
    items: list[str] = field(default_factory=list)

    @property
    def checked(self) -> dict[str, bool]:
        """Current state: {item: bool} for each item."""
        stored = self.value or {}
        return {item: stored.get(item, False) for item in self.items}

    @property
    def na(self) -> bool:
        """Whether N/A has been selected."""
        stored = self.value or {}
        return bool(stored.get("__na"))

    @property
    def is_complete(self) -> bool:
        return self.na or any(self.checked.values())

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "items": self.checked,
            "na": self.na,
        }

    def get_affordances(self) -> list[Affordance]:
        if self.na:
            return [
                SimpleButtonAffordance(
                    label="Clear N/A",
                    method="POST",
                    url=self.url,
                    body={"action": "clear_na"},
                    instruction="Clear N/A and allow item selection.",
                )
            ]
        return [
            CheckboxAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={item: "<true | false>" for item in self.items},
                instruction="Set one or more items. Omitted items are unchanged.",
                items=self.checked,
            ),
            SimpleButtonAffordance(
                label="N/A",
                method="POST",
                url=self.url,
                body={"action": "na"},
                instruction="Mark as not applicable. Clears all selections.",
            ),
        ]

    def _handle(self, body: dict) -> dict:
        action = body.get("action")
        if action == "na":
            # Clear all items and set N/A
            cleared = {item: False for item in self.items}
            cleared["__na"] = True
            self._store.set(self._scope, self.key, cleared)
        elif action == "clear_na":
            # Clear N/A, keep items at false
            cleared = {item: False for item in self.items}
            self._store.set(self._scope, self.key, cleared)
        else:
            current = self.checked
            for item_key, value in body.items():
                if item_key in current:
                    current[item_key] = value
            self._store.set(self._scope, self.key, current)
        return self.serialize()
