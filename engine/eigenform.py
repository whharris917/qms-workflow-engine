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
import dataclasses
import json
from dataclasses import dataclass
from html import escape
from typing import Any

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.store import Store


def render_dependency_line(depends_on, url_prefix: str = "") -> str:
    """Render a 'Depends on:' indicator for sibling-reading eigenforms."""
    if not depends_on:
        return ""
    deps = [depends_on] if isinstance(depends_on, str) else list(depends_on)
    parts = []
    for d in deps:
        path = f"{url_prefix}/{d}" if url_prefix else d
        parts.append(f'<code>{escape(path)}</code>')
    dep_html = ", ".join(parts)
    return (
        f'<div style="font-size: 11px; color: #999; margin-bottom: 4px;">'
        f'Depends on: {dep_html}'
        f'</div>'
    )

# Fields that belong to the base protocol, not type-specific config
_BASE_FIELDS = frozenset({"key", "label", "instruction", "editable", "_store", "_scope", "_url_prefix"})


def _is_json_safe(val) -> bool:
    """Check if a value can survive a JSON round-trip."""
    if val is None or isinstance(val, (bool, int, float, str)):
        return True
    if isinstance(val, (list, tuple)):
        return all(_is_json_safe(v) for v in val)
    if isinstance(val, dict):
        return all(isinstance(k, str) and _is_json_safe(v) for k, v in val.items())
    return False


@dataclass
class Eigenform:
    """Base protocol for all eigenform types."""
    key: str
    label: str
    instruction: str | None = None
    editable: bool = False

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
    def has_data(self) -> bool:
        """Whether this eigenform has user-entered data that can be cleared."""
        return self.value is not None

    def _clear_data(self):
        """Remove this eigenform's data from the store."""
        if self._store is not None:
            self._store.delete(self._scope, self.key)

    # --- Edit mode ---

    @property
    def edit_mode(self) -> bool:
        """Whether this eigenform is currently in edit mode."""
        if not self.editable or self._store is None:
            return False
        return bool(self._store.get(self._scope, f"{self.key}.__edit"))

    @property
    def effective_label(self) -> str:
        """The label to display — store override if set, else Python default."""
        if self._store is not None:
            override = self._store.get(self._scope, f"{self.key}.__label")
            if override is not None:
                return override
        return self.label

    @property
    def effective_instruction(self) -> str | None:
        """The instruction to display — store override if set, else Python default."""
        if self._store is not None:
            override = self._store.get(self._scope, f"{self.key}.__instruction")
            if override is not None:
                return override
        return self.instruction

    def _get_edit_affordances(self) -> list[Affordance]:
        """Affordances shown in edit mode. Subclasses extend this."""
        affs = [
            Affordance(
                label="Set Label",
                method="POST",
                url=self.url,
                body={"action": "set_label", "label": "<new label>"},
                instruction=f"Rename this eigenform. Current label: {self.effective_label}",
            ),
        ]
        current_instr = self.effective_instruction or ""
        affs.append(
            Affordance(
                label="Set Instruction",
                method="POST",
                url=self.url,
                body={"action": "set_instruction", "instruction": "<new instruction>"},
                instruction=f"Change the instruction text. Current: {current_instr}" if current_instr else "Set instruction text for this eigenform.",
            ),
        )
        return affs

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

    # --- Structural descriptors (Phase C) ---

    def _descriptor_config(self) -> dict:
        """Auto-extract serializable config from dataclass fields.

        Returns a dict of field_name -> value for all fields that are
        JSON-safe and not part of the base Eigenform protocol. Private
        fields (starting with _) are excluded.

        Subclasses may override to handle non-standard fields (e.g.,
        FieldDescriptor lists, callable-bearing fields).
        """
        config = {}
        for f in dataclasses.fields(type(self)):
            if f.name in _BASE_FIELDS or f.name.startswith("_"):
                continue
            val = getattr(self, f.name)
            if _is_json_safe(val):
                config[f.name] = val
        return config

    def to_descriptor(self) -> dict:
        """Serialize this eigenform's structural description.

        Returns a dict that, combined with the registry and optionally
        a seed eigenform, can reconstruct this eigenform. Containers
        override to include children.
        """
        desc = {"type": self.form, "key": self.key, "label": self.label}
        if self.instruction:
            desc["instruction"] = self.instruction
        config = self._descriptor_config()
        if config:
            desc["config"] = config
        return desc

    def _base_state(self) -> dict:
        """Return the state fields common to all eigenforms."""
        return {
            "form": self.form,
            "key": self.key,
            "label": self.effective_label,
            "instruction": self.effective_instruction,
        }

    def _serialize_state(self) -> dict:
        """Serialize this eigenform's state fields. Subclasses implement this."""
        raise NotImplementedError

    def _error(self, msg: str, *, action: str | None = None, body: dict | None = None) -> dict:
        """Return an error response with the current serialized state plus error metadata."""
        result = self.serialize()
        result["error"] = msg
        result["failed_action"] = action if action is not None else body
        return result

    def get_affordances(self) -> list[Affordance]:
        """Produce the affordances available on this eigenform."""
        return []

    def _serialize_full(self) -> dict:
        """Produce the full internal representation including render-only fields.

        Contains form, key, render_hints on affordances — everything the
        HTML renderer needs. Not intended for agent consumption.
        """
        state = self._serialize_state()
        state["complete"] = self.is_complete
        if self.editable:
            state["edit_mode"] = self.edit_mode
        affordances = []
        if self.edit_mode:
            affordances.extend(self._get_edit_affordances())
        else:
            affordances.extend(self.get_affordances())
        if self.has_data:
            affordances.append(SimpleButtonAffordance(
                label="Clear",
                method="POST",
                url=self.url,
                body={"action": "clear"},
                instruction=f"Clear all data from this {self.effective_label}.",
            ))
        if self.editable:
            # The chrome icon handles the mode switch visually;
            # this affordance exists for agent discoverability only.
            if self.edit_mode:
                affordances.append(Affordance(
                    label="Execute",
                    method="POST",
                    url=self.url,
                    body={"action": "set_mode", "mode": "execute"},
                    instruction="Switch to execution mode.",
                ))
            else:
                affordances.append(Affordance(
                    label="Edit",
                    method="POST",
                    url=self.url,
                    body={"action": "set_mode", "mode": "edit"},
                    instruction="Switch to edit mode.",
                ))
        state["affordances"] = [a.serialize() for a in affordances]
        # Mark the set_mode affordance as chrome-rendered (icon handles it)
        if self.editable:
            for aff in state["affordances"]:
                if aff.get("body", {}).get("action") == "set_mode":
                    aff["_chrome_rendered"] = True
        return state

    def serialize(self) -> dict | None:
        """Produce the agent-facing representation: clean, no render noise.

        Strips form, key, and render_hints from affordances — fields that
        exist only for HTML rendering and add noise for agents.
        """
        state = self._serialize_full()
        if state is None:
            return None
        state.pop("form", None)
        state.pop("key", None)
        for aff in state.get("affordances", []):
            aff.pop("render_hints", None)
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

        Uses _serialize_full() for HTML rendering (needs form, key,
        render_hints). The "See JSON" button shows the clean agent-facing
        serialize() output. After rendering, checks that all affordances
        were accounted for.
        """
        data = self._serialize_full()
        for aff in data.get("affordances", []):
            aff["_rendered"] = aff.pop("_chrome_rendered", False)
        inner = self.render_from_data(data)

        unrendered = [a for a in data.get("affordances", []) if not a.get("_rendered")]
        if unrendered:
            labels = [a.get("label", "?") for a in unrendered]
            raise RuntimeError(
                f"{type(self).__name__}(key={self.key!r}) did not render "
                f"{len(unrendered)} affordance(s): {labels}. "
                f"Use render_affordance_html() to render or Eigenform.mark_rendered() to skip."
            )

        json_str = escape(json.dumps(self.serialize(), indent=2))
        uid = self.uid

        complete_color = '#2a2' if self.is_complete else '#888'
        edit_border = ' border-style: dashed;' if self.edit_mode else ''

        # Mode switch icon for editable eigenforms
        mode_html = ''
        if self.editable:
            if self.edit_mode:
                # In edit mode: show play icon to return to execution mode
                btn_bg = "#fff3cd"
                btn_border = "#856404"
                icon_color = "#856404"
                mode_body = json.dumps({"action": "set_mode", "mode": "execute"})
                icon_svg = (
                    f'<svg viewBox="0 0 16 16" width="14" height="14" style="display:block;margin:auto;">'
                    f'<path d="M4 2.5l10 5.5-10 5.5z" fill="{icon_color}" stroke="none"/>'
                    f'</svg>'
                )
            else:
                # In execution mode: show pencil icon to enter edit mode
                btn_bg = "none"
                btn_border = "#aaa"
                icon_color = "#666"
                mode_body = json.dumps({"action": "set_mode", "mode": "edit"})
                icon_svg = (
                    f'<svg viewBox="0 0 16 16" width="14" height="14" style="display:block;margin:auto;">'
                    f'<path d="M11.5 1.5l3 3-9 9H2.5v-3z" fill="none" stroke="{icon_color}" stroke-width="1.5" stroke-linejoin="round"/>'
                    f'<path d="M9.5 3.5l3 3" fill="none" stroke="{icon_color}" stroke-width="1.5"/>'
                    f'</svg>'
                )
            mode_html = (
                f'<button onclick="fetch(\'{self.url}\','
                f'{{method:\'POST\',headers:{{\'Content-Type\':\'application/json\'}},'
                f'body:JSON.stringify({mode_body.replace(chr(34), "&quot;")})}}).then(()=>location.reload())"'
                f' style="position: absolute; top: 8px; left: 12px; cursor: pointer;'
                f' background: {btn_bg}; border: 1px solid {btn_border}; width: 24px; height: 24px;'
                f' border-radius: 3px; padding: 0; display: flex; align-items: center; justify-content: center;"'
                f' title="POST {self.url} {escape(mode_body)}">{icon_svg}</button>'
            )

        return (
            f'<div class="eigenform" data-form="{self.form}" data-key="{self.key}"'
            f' style="border: 2px solid {complete_color};{edit_border} padding: {"38px" if self.editable else "30px"} 12px 12px 12px; margin: 8px 0; position: relative;">'
            f'{mode_html}'
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
        action = body.get("action")
        if action == "batch":
            actions = body.get("actions", [])
            result = self.serialize()
            for action_body in actions:
                result = self.handle(action_body)
                if "error" in result:
                    return result
            return result
        if action == "clear":
            self._clear_data()
            return self.serialize()
        if action == "set_mode" and self.editable:
            mode = body.get("mode")
            if mode == "edit":
                self._store.set(self._scope, f"{self.key}.__edit", True)
            elif mode == "execute":
                self._store.set(self._scope, f"{self.key}.__edit", None)
            return self.serialize()
        if action == "set_label" and self.editable and self.edit_mode:
            new_label = body.get("label", "").strip()
            if not new_label:
                return self._error("Label cannot be empty.", action=action)
            self._store.set(self._scope, f"{self.key}.__label", new_label)
            return self.serialize()
        if action == "set_instruction" and self.editable and self.edit_mode:
            new_instr = body.get("instruction", "").strip()
            # Empty string clears the override (reverts to Python default)
            self._store.set(self._scope, f"{self.key}.__instruction", new_instr if new_instr else None)
            return self.serialize()
        return self._handle(body)

    def _handle(self, body: dict) -> dict:
        """Handle a single action. Subclasses must implement."""
        raise NotImplementedError
