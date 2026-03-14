"""Shared display helpers for workflow handlers."""


def trunc(val, length=80):
    """Truncate a string for display, adding ellipsis if needed."""
    if not val:
        return None
    return val[:length] + ("..." if len(val) > length else "")


def field(value, instruction=None):
    """Build a field object with value and optional instruction."""
    f = {"value": value}
    if instruction:
        f["instruction"] = instruction
    return f
