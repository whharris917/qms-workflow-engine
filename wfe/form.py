"""Form generation and validation for file-based node input.

Rather than filling fields one at a time via 'wfe fill', an agent can:
  1. Run 'wfe draft'   — engine writes a YAML form with inline instructions
  2. Edit the form     — agent reads and fills it in
  3. Run 'wfe submit'  — engine validates the form and fills all fields at once

This is the recommended input method for nodes with multiple fields or
fields requiring complex values (e.g., multi-line lists or node definitions).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from wfe.graph import Field, Node
    from wfe.template import TemplateLibrary

def form_file() -> Path:
    """Return the session-specific form file path."""
    import os
    session_id = os.environ.get("WFE_SESSION", "default")
    return Path(".wfe") / "sessions" / session_id / "form.yaml"


def write_form(
    node: "Node",
    graph_name: str,
    path: Path | None = None,
    templates: "TemplateLibrary | None" = None,
) -> Path:
    """Write a YAML form file for all writable fields on the node.

    The form includes inline instructions so an agent unfamiliar with the
    workflow can fill it correctly without additional context.

    If templates is provided and chain_template is already filled on the node,
    nodelist fields will show the actual template parameter keys as placeholders.
    """
    if path is None:
        path = form_file()
    path.parent.mkdir(parents=True, exist_ok=True)

    prompt = node.prompt or ""
    prompt_block = "\n".join(f"# {line}" if line else "#" for line in prompt.splitlines())

    lines = [
        "# ============================================================",
        f"# Graph: {graph_name}  |  Node: {node.id}",
        "# ============================================================",
    ]
    if prompt_block:
        lines.append("#")
        lines.append(prompt_block)
        lines.append("#")
    lines += [
        "# ============================================================",
        "# Fill in the fields below, then run:",
        "#",
        "#   wfe submit",
        "#",
        "# All required fields must be non-empty.",
        "# Errors are reported with specific guidance.",
        "# ============================================================",
        "",
    ]

    writable_fields = [f for f in node.fields.values() if f.writable]

    if not writable_fields:
        lines.append("# This node has no writable fields.")
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    for f in writable_fields:
        required = "required" if f.value is None else "optional"
        lines.append(f"# {f.name} [{f.type}, {required}]")

        hints = _field_hints(f.name, f.type)
        for hint in hints:
            lines.append(f"# {hint}")

        if f.type == "nodelist":
            lines.extend(_render_nodelist_field(f, node, templates))
        elif f.type == "text":
            lines.append(f"{f.name}:")
            if f.value and isinstance(f.value, list):
                for item in f.value:
                    lines.append(f"  - {item}")
            elif f.value:
                for item_line in str(f.value).splitlines():
                    if item_line.strip():
                        lines.append(f"  - {item_line.strip()}")
            lines.append("")
        else:
            val = f.value if f.value is not None else ""
            rendered = yaml.dump({f.name: val}, default_flow_style=False).rstrip()
            lines.append(rendered)
            lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_nodelist_field(
    f: "Field",
    node: "Node",
    templates: "TemplateLibrary | None",
) -> list[str]:
    """Render a nodelist field as a YAML list of dicts."""
    lines = []
    lines.append("# Add one YAML dict entry (starting with '-') per node.")
    lines.append(f"{f.name}:")

    if f.value and isinstance(f.value, list):
        # Render existing value
        for entry in f.value:
            if isinstance(entry, dict):
                first = True
                for k, v in entry.items():
                    prefix = "  - " if first else "    "
                    v_str = yaml.dump(v, default_flow_style=True).strip()
                    lines.append(f"{prefix}{k}: {v_str}")
                    first = False
            else:
                lines.append(f"  - {entry}")
    else:
        lines.append("  - {}  # Replace with required keys (see hints above)")
        lines.append("  # Add more entries as needed (copy the block above)")

    lines.append("")
    return lines


def _field_hints(name: str, ftype: str) -> list[str]:
    """Return helpful hint lines for known field names."""
    hints = {
        "workflow_name": [
            "Name for the new workflow.",
            "Output: workflows/<workflow_name>.yaml",
            "Use letters, digits, hyphens, and underscores only.",
        ],
        "template_id": [
            "Unique identifier for this template.",
            "Output: templates/<template_id>.yaml",
            "Use letters, digits, hyphens, and underscores only.",
        ],
        "nodes": [
            "One entry per node. Two formats are supported:",
            "",
            "Template-based (shorthand):",
            "  - template: ei",
            "    task_description: Do the first thing",
            "    vr_required: false",
            "",
            "Inline (longhand — define the node structure directly):",
            "  - id: define",
            "    prompt: Fill all fields, then advance.",
            "    fields:",
            "      - name: my_field",
            "        type: string",
            "    exit_hooks:",
            "      - my_hook",
            "",
            "Nodes auto-wire in order (node_i -> node_i+1).",
            "Add 'edges: []' to make a node a terminal with no outgoing edges.",
            "Run 'wfe template list' to see available templates.",
        ],
        "fields": [
            "One field definition per entry.",
            "Required keys: name, type",
            "Optional keys: parameter (bool, default: false), writable (bool, default: true), default",
            "Example:",
            "  - name: task_description",
            "    type: string",
            "    parameter: true",
            "    writable: false",
            "  - name: outcome",
            "    type: string",
            "    writable: true",
        ],
        "edge_templates": [
            "One edge definition per entry.",
            "Required keys: to (symbolic target, e.g. \"{next}\", \"{var}\", \"{vr}\")",
            "Optional keys: condition (e.g. outcome==Pass)",
            "Example:",
            "  - to: \"{next}\"",
            "    condition: outcome==Pass",
            "  - to: \"{var}\"",
            "    condition: outcome==Fail",
        ],
        "enter_hooks": [
            "Hook names fired when a node of this type is entered. One per line.",
        ],
        "exit_hooks": [
            "Hook names fired when a node of this type is exited. One per line.",
        ],
    }
    return hints.get(name, [])


def read_and_validate(
    path: Path,
    node: "Node",
    templates: "TemplateLibrary | None" = None,
) -> tuple[dict[str, Any], list[str]]:
    """Read a form file and validate it against the node's writable fields.

    Returns:
        (values, errors)
        - values: dict of field_name -> value, ready to pass to fill_field
        - errors: list of error messages; empty if valid
    """
    if not path.exists():
        return {}, [f"Form file not found: {path}. Run 'wfe draft' first."]

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        return {}, [f"YAML parse error in form file: {e}"]

    if not isinstance(data, dict):
        return {}, ["Form file must be a YAML mapping (key: value pairs)."]

    errors: list[str] = []
    values: dict[str, Any] = {}

    writable = {f.name: f for f in node.fields.values() if f.writable}

    for fname, f in writable.items():
        raw = data.get(fname)
        is_required = f.value is None

        if f.type == "nodelist":
            if raw is None or raw == [] or raw == "":
                if is_required:
                    errors.append(
                        f"  '{fname}': required but empty. "
                        "Add at least one node entry as a YAML dict (- key: value)."
                    )
                continue
            if not isinstance(raw, list):
                errors.append(
                    f"  '{fname}': must be a YAML list of dicts "
                    f"(found {type(raw).__name__}). Use '- key: value' format."
                )
                continue
            node_entries = []
            for i, entry in enumerate(raw, start=1):
                if not isinstance(entry, dict):
                    errors.append(
                        f"  '{fname}' entry {i}: must be a dict "
                        f"(found {type(entry).__name__}). Use '- key: value' format."
                    )
                    continue
                if not entry:
                    errors.append(f"  '{fname}' entry {i}: is empty. Fill in all required fields.")
                    continue
                node_entries.append(entry)
            if not node_entries and is_required:
                errors.append(f"  '{fname}': contains no valid entries.")
                continue
            values[fname] = node_entries

        elif f.type == "text":
            if raw is None or raw == "" or raw == []:
                if is_required:
                    errors.append(
                        f"  '{fname}': required but empty. "
                        "Add at least one item as a YAML list entry (- value)."
                    )
                continue
            if isinstance(raw, list):
                items = [str(i).strip() for i in raw if str(i).strip()]
            else:
                items = [
                    line.strip()
                    for line in str(raw).splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
            if not items:
                if is_required:
                    errors.append(f"  '{fname}': required but contains no valid items.")
                continue
            values[fname] = items

        else:
            val = "" if raw is None else str(raw).strip()
            if is_required and not val:
                errors.append(f"  '{fname}': required but empty.")
                continue
            values[fname] = val

    # Unknown fields in the form (warn, don't error)
    unknown = [k for k in data if k not in writable and not str(k).startswith("_")]
    if unknown:
        errors.append(
            f"  Unrecognized field(s) in form: {', '.join(str(k) for k in unknown)}. "
            "Check spelling against the field names in 'wfe view'."
        )

    if errors:
        return {}, errors

    # Semantic validation
    errors.extend(_validate_semantics(values, templates))
    return (values, errors) if not errors else ({}, errors)


def _validate_semantics(
    values: dict[str, Any],
    templates: "TemplateLibrary | None",
) -> list[str]:
    errors: list[str] = []

    workflow_name = values.get("workflow_name", "")
    if workflow_name and not re.match(r"^[a-zA-Z0-9_\-]+$", workflow_name):
        errors.append(
            f"  'workflow_name' {workflow_name!r} contains invalid characters. "
            "Use only letters, digits, hyphens, and underscores."
        )

    # Validate each nodes entry has a template key and matching parameters
    nodes_list = values.get("nodes", [])
    if nodes_list and templates is not None:
        for i, entry in enumerate(nodes_list, start=1):
            tmpl_id = entry.get("template", "")
            if not tmpl_id:
                continue  # Inline entry — hook performs domain validation
            try:
                tmpl = templates.get(str(tmpl_id))
            except KeyError:
                available = ", ".join(templates.list_ids()) or "(none)"
                errors.append(
                    f"  'nodes' entry {i}: template {tmpl_id!r} not found. "
                    f"Available: {available}"
                )
                continue
            expected_keys = {s.name for s in tmpl.field_specs if s.parameter}
            actual_keys = set(entry.keys()) - {"template"}
            missing = expected_keys - actual_keys
            extra = actual_keys - expected_keys
            if missing:
                errors.append(
                    f"  'nodes' entry {i} (template={tmpl_id!r}): "
                    f"missing field(s): {', '.join(sorted(missing))}."
                )
            if extra:
                errors.append(
                    f"  'nodes' entry {i} (template={tmpl_id!r}): "
                    f"unexpected field(s): {', '.join(sorted(extra))}. "
                    f"Expected: {', '.join(sorted(expected_keys))}"
                )

    return errors
