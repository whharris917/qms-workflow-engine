"""MultiForm — groups multiple eigenforms under a single affordance.

All fields are submitted together in one POST, reducing agent round-trips.
The individual fields are value descriptors, not eigenforms — they have
no independent identity, affordances, or rendering. The multi_field owns
them entirely.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from html import escape
from typing import Any

from engine.affordances import Affordance
from engine.eigenform import Eigenform
from engine.templates import render_template


@dataclass
class FieldDescriptor:
    """A single field within a MultiForm. Not an eigenform."""
    key: str
    label: str
    type: str = "text"  # text | choice
    instruction: str | None = None
    options: list[str] | None = None  # for choice type


class SetFieldsAffordance(Affordance):
    """An affordance that sets multiple fields at once."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None,
                 fields: list[FieldDescriptor] | None = None,
                 values: dict | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.fields = fields or []
        self.values = values or {}

    def _render_hints(self) -> dict:
        return {
            "type": "multi_field",
            "fields": [
                {"key": fd.key, "label": fd.label, "type": fd.type,
                 "instruction": fd.instruction, "options": fd.options}
                for fd in self.fields
            ],
            "values": self.values,
        }


@dataclass
class MultiForm(Eigenform):
    """Groups multiple fields under a single affordance.

    Fields are value descriptors (FieldDescriptor), not eigenforms.
    They have no independent identity or affordances. The MultiForm
    owns them entirely and submits them as one unit.
    """
    fields: list[FieldDescriptor] = field(default_factory=list)

    def _descriptor_config(self) -> dict:
        """Serialize FieldDescriptors to plain dicts for the descriptor."""
        return {
            "fields": [
                {k: v for k, v in {
                    "key": fd.key, "label": fd.label, "type": fd.type,
                    "instruction": fd.instruction, "options": fd.options,
                }.items() if v is not None}
                for fd in self.fields
            ]
        }

    def _apply_descriptor(self, desc: dict):
        """Override base: convert config['fields'] dicts back to FieldDescriptors
        when applying a descriptor onto this instance.
        """
        super()._apply_descriptor(desc)
        cfg_fields = (desc.get("config") or {}).get("fields")
        if cfg_fields is not None:
            self.fields = [
                FieldDescriptor(
                    key=f["key"], label=f.get("label", f["key"]),
                    type=f.get("type", "text"),
                    instruction=f.get("instruction"),
                    options=f.get("options"),
                )
                for f in cfg_fields
            ]

    @property
    def values(self) -> dict:
        stored = self.value
        if stored and isinstance(stored, dict):
            return stored
        return {}

    @property
    def is_complete(self) -> bool:
        for fd in self.fields:
            val = self.values.get(fd.key)
            if val is None or val == "":
                return False
        return True

    def _serialize_state(self) -> dict:
        vals = self.values
        serialized_fields = []
        for fd in self.fields:
            f = {
                "key": fd.key,
                "label": fd.label,
                "type": fd.type,
                "value": vals.get(fd.key),
            }
            if fd.instruction:
                f["instruction"] = fd.instruction
            if fd.options:
                f["options"] = fd.options
            serialized_fields.append(f)
        return self._base_state() | {
            "fields": serialized_fields,
        }

    def render_from_data(self, data: dict) -> str:
        return render_template("multi.html", data=data, ef=self,
                               url=self.url, label=data["label"],
                               instruction=data.get("instruction") or "")

    def get_affordances(self) -> list[Affordance]:
        body = {}
        for fd in self.fields:
            if fd.type == "choice" and fd.options:
                body[fd.key] = f"<{' | '.join(fd.options)}>"
            else:
                body[fd.key] = f"<{fd.label}>"
        return [
            SetFieldsAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body=body,
                instruction=f"Set all fields for {self.label}. All fields are optional; omitted fields are unchanged.",
                fields=self.fields,
                values=self.values,
            )
        ]

    def _get_edit_affordances(self) -> list[Affordance]:
        affs = super()._get_edit_affordances()
        affs.append(Affordance(
            label="Add Field", method="POST", url=self.url,
            body={"action": "add_field", "key": "<key>", "field_label": "<label>",
                  "type": "<text | choice>", "options": "<comma-separated, for choice type>"},
            instruction="Add a new field. type defaults to 'text'. options only needed for choice type.",
        ))
        if self.fields:
            keys = " | ".join(fd.key for fd in self.fields)
            affs.append(Affordance(
                label="Remove Field", method="POST", url=self.url,
                body={"action": "remove_field", "key": f"<{keys}>"},
                instruction="Remove a field by key.",
            ))
        return affs

    def _handle(self, body: dict) -> dict:
        action = body.get("action")

        # Edit-mode config actions
        if action == "add_field" and self.editable and self.edit_mode:
            key = body.get("key", "").strip()
            if not key or key.startswith("<"):
                return self._error("Field key is required.", body=body)
            existing_keys = {fd.key for fd in self.fields}
            if key in existing_keys:
                return self._error(f"Field key '{key}' already exists.", body=body)
            new_field = FieldDescriptor(
                key=key,
                label=body.get("field_label", key).strip() or key,
                type=body.get("type", "text").strip() or "text",
            )
            if new_field.type not in ("text", "choice"):
                return self._error(f"Invalid field type: {new_field.type}. Must be 'text' or 'choice'.", body=body)
            opts_raw = body.get("options", "")
            if opts_raw and not opts_raw.startswith("<"):
                new_field.options = [o.strip() for o in opts_raw.split(",") if o.strip()]
            self._push_undo()
            new_fields = list(self.fields) + [new_field]
            new_dicts = [
                {k: v for k, v in {
                    "key": fd.key, "label": fd.label, "type": fd.type,
                    "instruction": fd.instruction, "options": fd.options,
                }.items() if v is not None}
                for fd in new_fields
            ]
            self._set_my_config("fields", new_dicts)
            self.fields = new_fields
            return self.serialize()

        if action == "remove_field" and self.editable and self.edit_mode:
            key = body.get("key", "")
            before_count = len(self.fields)
            new_fields = [fd for fd in self.fields if fd.key != key]
            if len(new_fields) == before_count:
                valid = " | ".join(fd.key for fd in self.fields)
                return self._error(f"No field with key '{key}'. Valid: {valid}", body=body)
            self._push_undo()
            new_dicts = [
                {k: v for k, v in {
                    "key": fd.key, "label": fd.label, "type": fd.type,
                    "instruction": fd.instruction, "options": fd.options,
                }.items() if v is not None}
                for fd in new_fields
            ]
            self._set_my_config("fields", new_dicts)
            self.fields = new_fields
            # Clean up stored value for removed field
            current = dict(self.values)
            current.pop(key, None)
            if current:
                self._store.set(self._scope, self.key, current)
            return self.serialize()

        # Normal value setting
        current = dict(self.values)
        valid_keys = {fd.key for fd in self.fields}
        for key, value in body.items():
            if key in valid_keys and value != "":
                current[key] = value
        self._store.set(self._scope, self.key, current)
        return self.serialize()
