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
from engine.eigenforms import Eigenform


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

    def render_html(self) -> str:
        endpoint = f'{self.method} {self.url}'

        # Build a form with one input per field
        js_keys = []
        inputs = ""
        for fd in self.fields:
            current = self.values.get(fd.key)
            display = escape(str(current)) if current is not None else ""

            if fd.type == "choice" and fd.options:
                inputs += f'<div style="margin: 4px 0;"><label>{escape(fd.label)}: '
                inputs += f'<select name="{fd.key}">'
                inputs += f'<option value="">--</option>'
                for opt in fd.options:
                    selected = " selected" if opt == current else ""
                    inputs += f'<option value="{escape(opt)}"{selected}>{escape(opt)}</option>'
                inputs += '</select></label>'
                if fd.instruction:
                    inputs += f' <span style="font-size: 11px; color: #888;">{escape(fd.instruction)}</span>'
                inputs += '</div>'
            else:
                inputs += (
                    f'<div style="margin: 4px 0;"><label>{escape(fd.label)}: '
                    f'<input name="{fd.key}" type="text" value="{display}" style="width: 200px;" />'
                    f'</label>'
                )
                if fd.instruction:
                    inputs += f' <span style="font-size: 11px; color: #888;">{escape(fd.instruction)}</span>'
                inputs += '</div>'

            js_keys.append(fd.key)

        # Build JS that collects all fields into one object
        js_collect = "var b={};"
        for k in js_keys:
            js_collect += f"b['{k}']=this.elements['{k}'].value;"

        return (
            f'<form onsubmit="'
            f"{js_collect}"
            f"fetch('{self.url}',{{method:'POST',headers:{{'Content-Type':'application/json'}},"
            f"body:JSON.stringify(b)}}).then(()=>location.reload()); return false\">"
            f'{inputs}'
            f'<button type="submit" style="margin-top: 4px;"'
            f' title="{escape(endpoint)} {escape(json.dumps(self.body))}">'
            f'{escape(self.label)}</button>'
            f'</form>'
        )


@dataclass
class MultiForm(Eigenform):
    """Groups multiple fields under a single affordance.

    Fields are value descriptors (FieldDescriptor), not eigenforms.
    They have no independent identity or affordances. The MultiForm
    owns them entirely and submits them as one unit.
    """
    fields: list[FieldDescriptor] = field(default_factory=list)

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
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
            "fields": serialized_fields,
        }

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

    def render_inner(self, affordances: list[Affordance]) -> str:
        html = f'<h3>{self.label}</h3>'
        if self.instruction:
            html += f'<p>{self.instruction}</p>'
        for aff in affordances:
            html += aff.render()
        return html

    def handle(self, body: dict) -> dict:
        current = dict(self.values)
        valid_keys = {fd.key for fd in self.fields}
        for key, value in body.items():
            if key in valid_keys and value != "":
                current[key] = value
        self._store.set(self._scope, self.key, current)
        return self.serialize()
