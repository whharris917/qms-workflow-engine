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
        """Serialize FieldDescriptors to plain dicts."""
        return {
            "fields": [
                {k: v for k, v in {
                    "key": fd.key, "label": fd.label, "type": fd.type,
                    "instruction": fd.instruction, "options": fd.options,
                }.items() if v is not None}
                for fd in self.fields
            ]
        }

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
        return render_template("multi.html", data=data, ef=self)

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

    def _handle(self, body: dict) -> dict:
        current = dict(self.values)
        valid_keys = {fd.key for fd in self.fields}
        for key, value in body.items():
            if key in valid_keys and value != "":
                current[key] = value
        self._store.set(self._scope, self.key, current)
        return self.serialize()
