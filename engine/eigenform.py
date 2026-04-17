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
        bound._migrate_legacy_overrides()
        bound._bind_children(store, url_prefix)
        return bound

    # --- Descriptor as single source of truth ---

    def _get_my_descriptor(self) -> dict | None:
        """Return this eigenform's entry in the parent container's __structure.

        Returns None if no parent structure exists or this eigenform isn't
        in it (e.g., top-level seed before first __structure write).
        """
        if self._store is None or self._scope is None:
            return None
        structure = self._store.get(self._scope, "__structure")
        if not structure:
            return None
        for desc in structure:
            if desc.get("key") == self.key:
                return desc
        return None

    def _set_my_field(self, name: str, value):
        """Set a top-level field (label, instruction, editable) in my descriptor.

        The parent's __structure is the canonical record. Also updates
        self.{name} so the runtime instance stays consistent within this
        request before the next bind.
        """
        if self._store is None or self._scope is None:
            return
        structure = self._store.get(self._scope, "__structure") or []
        for desc in structure:
            if desc.get("key") == self.key:
                if value is None:
                    desc.pop(name, None)
                else:
                    desc[name] = value
                self._store.set(self._scope, "__structure", structure)
                setattr(self, name, value)
                return

    def _set_my_config(self, name: str, value):
        """Set a config-level field (mode, multiline, min_length, …) in my descriptor.

        Also updates self.{name} so the runtime instance reflects the change
        within this request.
        """
        if self._store is None or self._scope is None:
            return
        structure = self._store.get(self._scope, "__structure") or []
        for desc in structure:
            if desc.get("key") == self.key:
                cfg = desc.setdefault("config", {})
                cfg[name] = value
                if not cfg:
                    desc.pop("config", None)
                self._store.set(self._scope, "__structure", structure)
                setattr(self, name, value)
                return

    def _apply_descriptor(self, desc: dict):
        """Apply scalar fields from a descriptor onto this instance.

        Called by from_descriptor on the seed-match path so the descriptor
        wins over the seed's defaults. Subclasses override to handle
        non-scalar fields (e.g., MultiForm.fields = list[FieldDescriptor]).
        """
        if "label" in desc:
            self.label = desc["label"]
        if "instruction" in desc:
            self.instruction = desc["instruction"]
        self.editable = bool(desc.get("editable", False))
        for k, v in (desc.get("config") or {}).items():
            setattr(self, k, v)

    def _migrate_legacy_overrides(self):
        """Fold any legacy __config/__label/__instruction entries for this
        eigenform into the parent's __structure descriptor, then delete them.

        This runs once per bind. After migration, __structure is the only
        place these fields are stored; subsequent reads come from self.{field}.
        """
        if self._store is None or self._scope is None:
            return
        legacy_label = self._store.get(self._scope, f"{self.key}.__label")
        legacy_instr = self._store.get(self._scope, f"{self.key}.__instruction")
        legacy_cfg = self._store.get(self._scope, f"{self.key}.__config")
        if legacy_label is None and legacy_instr is None and legacy_cfg is None:
            return
        structure = self._store.get(self._scope, "__structure")
        if not structure:
            return
        changed = False
        for desc in structure:
            if desc.get("key") != self.key:
                continue
            if legacy_label is not None:
                desc["label"] = legacy_label
                changed = True
            if legacy_instr is not None:
                desc["instruction"] = legacy_instr
                changed = True
            if legacy_cfg is not None:
                cfg = desc.setdefault("config", {})
                cfg.update(legacy_cfg)
                changed = True
            break
        if changed:
            self._store.set(self._scope, "__structure", structure)
            # Re-apply the freshly-folded descriptor onto this instance
            # so the runtime reflects the migrated overrides.
            for desc in structure:
                if desc.get("key") == self.key:
                    self._apply_descriptor(desc)
                    break
        if legacy_label is not None:
            self._store.delete(self._scope, f"{self.key}.__label")
        if legacy_instr is not None:
            self._store.delete(self._scope, f"{self.key}.__instruction")
        if legacy_cfg is not None:
            self._store.delete(self._scope, f"{self.key}.__config")

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

    def _snapshot_edit_state(self) -> dict:
        """Capture current edit state by snapshotting this eigenform's entry
        in the parent's __structure. Subclasses extend to include child data
        scopes that live outside the descriptor (e.g., child stores).
        """
        import copy as _copy
        desc = self._get_my_descriptor()
        return {"__descriptor": _copy.deepcopy(desc) if desc else None}

    def _restore_edit_state(self, state: dict):
        """Restore the descriptor entry from a snapshot and re-apply scalar
        fields to this instance so the runtime reflects the restoration.
        """
        snap = state.get("__descriptor")
        if snap is None or self._store is None or self._scope is None:
            return
        structure = self._store.get(self._scope, "__structure") or []
        replaced = False
        for i, desc in enumerate(structure):
            if desc.get("key") == self.key:
                structure[i] = snap
                replaced = True
                break
        if not replaced:
            structure.append(snap)
        self._store.set(self._scope, "__structure", structure)
        self._apply_descriptor(snap)

    def _push_undo(self):
        """Snapshot current edit state and push to undo stack."""
        snapshot = self._snapshot_edit_state()
        stack = self._store.get(self._scope, f"{self.key}.__undo") or []
        stack.append(snapshot)
        self._store.set(self._scope, f"{self.key}.__undo", stack)

    @property
    def _undo_depth(self) -> int:
        """Number of undo steps available."""
        stack = self._store.get(self._scope, f"{self.key}.__undo") or []
        return len(stack)

    def _get_edit_affordances(self) -> list[Affordance]:
        """Affordances shown in edit mode. Subclasses extend this."""
        affs = [
            Affordance(
                label="Set Label",
                method="POST",
                url=self.url,
                body={"action": "set_label", "label": "<new label>"},
                instruction=f"Rename this eigenform. Current label: {self.label}",
            ),
        ]
        current_instr = self.instruction or ""
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
        if self.editable:
            desc["editable"] = True
        config = self._descriptor_config()
        if config:
            desc["config"] = config
        return desc

    def _base_state(self) -> dict:
        """Return the state fields common to all eigenforms."""
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
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
            _aff = SimpleButtonAffordance(
                label="Clear",
                method="POST",
                url=self.url,
                body={"action": "clear"},
                instruction=f"Clear all data from this {self.label}.",
            )
            _aff._floatable = "clear"
            affordances.append(_aff)
        if self.editable:
            # Chrome icons handle these visually; affordances exist for agent discoverability.
            if self.edit_mode:
                affordances.append(Affordance(
                    label="Execute",
                    method="POST",
                    url=self.url,
                    body={"action": "set_mode", "mode": "execute"},
                    instruction="Switch to execution mode.",
                ))
                if self._undo_depth > 0:
                    affordances.append(Affordance(
                        label="Undo",
                        method="POST",
                        url=self.url,
                        body={"action": "undo"},
                        instruction=f"Undo the last edit-mode change ({self._undo_depth} available).",
                    ))
                affordances.append(Affordance(
                    label="Discard",
                    method="POST",
                    url=self.url,
                    body={"action": "discard"},
                    instruction="Discard all edit-mode changes and return to execution mode.",
                ))
            else:
                _aff = Affordance(
                    label="Edit",
                    method="POST",
                    url=self.url,
                    body={"action": "set_mode", "mode": "edit"},
                    instruction="Switch to edit mode.",
                )
                _aff._floatable = "edit"
                affordances.append(_aff)
        _aff = Affordance(
            label="Batch",
            method="POST",
            url=self.url,
            body={"action": "batch", "actions": ["<action_body_1>", "<action_body_2>", "..."]},
            instruction=(
                "Execute multiple actions in a single request. "
                "Each entry in 'actions' uses the same body format as this eigenform's other affordances. "
                "Actions run sequentially; execution stops on first error."
            ),
        )
        _aff._floatable = "batch"
        affordances.append(_aff)
        serialized_affs = []
        for a in affordances:
            d = a.serialize()
            fkey = getattr(a, '_floatable', None)
            if fkey is not None:
                d["_floatable"] = fkey
            # Carry through navigation option dicts (O(N)→O(1) collapse)
            for attr in ('_tabs', '_sections', '_steps'):
                val = getattr(a, attr, None)
                if val is not None:
                    d[attr.lstrip('_')] = val
            if getattr(a, '_chrome_rendered', False):
                d["_chrome_rendered"] = True
            serialized_affs.append(d)
        state["affordances"] = serialized_affs
        # Mark chrome-rendered affordances (no visual button needed in HTML)
        chrome_actions = {"batch"}
        if self.editable:
            chrome_actions |= {"set_mode", "undo", "discard"}
        for aff in state["affordances"]:
            if aff.get("body", {}).get("action") in chrome_actions:
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
            aff.pop("_chrome_rendered", None)
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

# Forms that are containers (transparent wrapper, no card styling in themes)
    _CONTAINER_FORMS = {"page", "navigation", "group", "visibility", "switch", "repeater"}

    def render(self) -> str:
        """Render this eigenform as HTML, wrapped in a themed container.

        Uses _serialize_full() for HTML rendering (needs form, key,
        render_hints). The "See JSON" button shows the clean agent-facing
        serialize() output. After rendering, checks that all affordances
        were accounted for.

        The wrapper HTML is generated by a Jinja2 template (wrapper.html),
        which themes can override (e.g. sleek/wrapper.html) to control the
        full output structure without CSS hiding tricks.
        """
        from engine.templates import render_template

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

        classes = ['eigenform']
        if self.is_complete:
            classes.append('eigenform--complete')
        if self.edit_mode:
            classes.append('eigenform--editing')
        if self.editable:
            classes.append('eigenform--editable')

        return render_template("wrapper.html",
            classes=classes,
            form=self.form,
            key=self.key,
            uid=self.uid,
            label=self.label,
            instruction=self.instruction or "",
            editable=self.editable,
            edit_mode=self.edit_mode,
            undo_count=self._undo_depth,
            url=self.url,
            inner=inner,
            json_str=json.dumps(self.serialize(), indent=2, ensure_ascii=False),
            is_container=self.form in self._CONTAINER_FORMS,
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
                # Snapshot initial state for discard
                self._store.set(self._scope, f"{self.key}.__snapshot", self._snapshot_edit_state())
                self._store.set(self._scope, f"{self.key}.__undo", [])
            elif mode == "execute":
                self._store.set(self._scope, f"{self.key}.__edit", None)
                self._store.set(self._scope, f"{self.key}.__snapshot", None)
                self._store.set(self._scope, f"{self.key}.__undo", None)
            return self.serialize()
        if action == "undo" and self.editable and self.edit_mode:
            stack = self._store.get(self._scope, f"{self.key}.__undo") or []
            if stack:
                state = stack.pop()
                self._store.set(self._scope, f"{self.key}.__undo", stack)
                self._restore_edit_state(state)
            return self.serialize()
        if action == "discard" and self.editable and self.edit_mode:
            snapshot = self._store.get(self._scope, f"{self.key}.__snapshot")
            if snapshot:
                self._restore_edit_state(snapshot)
            self._store.set(self._scope, f"{self.key}.__edit", None)
            self._store.set(self._scope, f"{self.key}.__snapshot", None)
            self._store.set(self._scope, f"{self.key}.__undo", None)
            return self.serialize()
        if action == "set_label" and self.editable and self.edit_mode:
            self._push_undo()
            new_label = body.get("label", "").strip()
            if not new_label:
                return self._error("Label cannot be empty.", action=action)
            self._set_my_field("label", new_label)
            return self.serialize()
        if action == "set_instruction" and self.editable and self.edit_mode:
            self._push_undo()
            new_instr = body.get("instruction", "").strip()
            self._set_my_field("instruction", new_instr if new_instr else None)
            return self.serialize()
        return self._handle(body)

    def _handle(self, body: dict) -> dict:
        """Handle a single action. Subclasses must implement."""
        raise NotImplementedError
