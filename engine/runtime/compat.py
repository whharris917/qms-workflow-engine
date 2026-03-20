"""Backward-compatibility normalizer.

Expands old YAML shorthand forms into the canonical schema
so the runtime only needs to handle one format.
"""

from __future__ import annotations


def normalize_definition(raw: dict) -> dict:
    """Normalize a raw YAML dict into canonical schema form.

    Handles:
    - proceed.requires shorthand → proceed.gate expression tree
    - Missing workflow_id → derived from workflow_title
    - Old field format without explicit key → uses dict key as key
    - Top-level submodules/sdlc_governed → option_sets
    - options_ref → options_from
    - computed: sdlc_check → compute expression
    - CR handler side effects (affects_code/affects_submodule cascades)
    """
    d = dict(raw)

    # Ensure workflow_id exists
    if "workflow_id" not in d:
        title = d.get("workflow_title", "untitled")
        d["workflow_id"] = title.lower().replace(" ", "-")

    # Migrate top-level option lists to option_sets
    if "option_sets" not in d:
        option_sets = {}
        for key in list(d.keys()):
            if key not in ("workflow_id", "workflow_title", "workflow_description",
                           "nodes", "column_types", "option_sets"):
                val = d.get(key)
                if isinstance(val, list):
                    option_sets[key] = val
        if option_sets:
            d["option_sets"] = option_sets

    # Normalize nodes
    nodes = d.get("nodes", {})
    for nid, ndef in nodes.items():
        _normalize_node(ndef)

    return d


def _normalize_node(ndef: dict):
    """Normalize a single node definition in place."""
    # Normalize proceed gate
    proceed = ndef.get("proceed")
    if proceed and "gate" not in proceed:
        requires = proceed.get("requires", [])
        if requires:
            proceed["gate"] = {
                "op": "AND",
                "conditions": [
                    {"type": "field_truthy", "key": k} for k in requires
                ],
            }

    # Normalize field definitions
    fields = ndef.get("fields")
    if fields:
        for fid, fdef in fields.items():
            if "key" not in fdef:
                fdef["key"] = fid
            _normalize_field(fdef)


def _normalize_field(fdef: dict):
    """Normalize a single field definition in place."""
    # options_ref → options_from
    if "options_ref" in fdef and "options_from" not in fdef:
        fdef["options_from"] = fdef.pop("options_ref")

    # annotate_from stays as-is (same name in both schemas)

    # computed: sdlc_check → compute expression
    if fdef.get("type") == "computed" and "computed" in fdef:
        computed_name = fdef.pop("computed")
        if computed_name == "sdlc_check":
            # The key for sdlc_check is the field's own key (which points to
            # the submodule value). The set is sdlc_governed.
            fdef["compute"] = {
                "type": "set_membership",
                "key": fdef.get("key", ""),
                "set_ref": "sdlc_governed",
            }

    # Inject side effects for known CR patterns
    # affects_code = false → clear affects_submodule and submodule
    if fdef.get("key") == "affects_code" and fdef.get("type") == "boolean":
        if not fdef.get("side_effects"):
            fdef["side_effects"] = [
                {
                    "when": {"type": "field_equals", "key": "affects_code", "value": False},
                    "set": {"affects_submodule": False, "submodule": None},
                }
            ]

    # affects_submodule = false → clear submodule
    if fdef.get("key") == "affects_submodule" and fdef.get("type") == "boolean":
        if not fdef.get("side_effects"):
            fdef["side_effects"] = [
                {
                    "when": {"type": "field_equals", "key": "affects_submodule", "value": False},
                    "set": {"submodule": None},
                }
            ]
