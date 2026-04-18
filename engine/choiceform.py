"""ChoiceForm — single selection from a list of options.

`options` may hold either a literal list (editable in-place via the ListForm
child, stored in `__options`) or a `SiblingBind` that resolves the option
list from another component's current value at serialize time. When the
bound sibling changes and the currently selected value is no longer in the
resolved list, the selection is flagged `stale` and a Clear affordance is
offered — replacing what used to be a separate DynamicChoiceForm class.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.affordances import Affordance, SimpleButtonAffordance
from engine.component import Component
from engine.sibling_bind import SiblingBind
from engine.templates import render_template


class SelectAffordance(Affordance):
    """An affordance that selects one option from a list."""

    def __init__(self, label: str, method: str, url: str, body: dict,
                 instruction: str | None = None, options: list[str] | None = None,
                 current: str | None = None):
        super().__init__(label=label, method=method, url=url, body=body, instruction=instruction)
        self.options = options or []
        self.current = current

    def _render_hints(self) -> dict:
        return {"type": "radio", "options": self.options, "current": self.current}


@dataclass
class ChoiceForm(Component):
    """Single selection from a (possibly reactive) set of options."""
    form = "choice"

    options: "list[str] | SiblingBind" = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        # Only create the editable-options child when options are literal.
        # Reactive options (SiblingBind) are derived from a sibling and
        # have no locally-editable list representation.
        if not isinstance(self.options, SiblingBind):
            from engine.listform import ListForm
            self._options_form = ListForm(
                key="__options",
                label="Options",
                allow_constraints=False,
            )
        else:
            self._options_form = None

    @property
    def _has_reactive_options(self) -> bool:
        return isinstance(self.options, SiblingBind)

    @property
    def children(self) -> list[Component]:
        if self._has_reactive_options:
            return []
        if self.edit_mode:
            return [self._options_form]
        return []

    def _bind_children(self, store, url_prefix):
        if self._has_reactive_options:
            return
        from engine.listform import ListForm
        self._options_form = self._options_form.bind(
            store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
        # Seed initial options if no ListForm data exists yet
        if not self._options_form.value:
            for opt in self.options:
                self._options_form.handle({"action": "add", "value": opt})
        # Wrap child handle so ChoiceForm pushes undo before ListForm changes
        original_handle = self._options_form.handle
        parent = self
        def _handle_with_undo(body):
            if parent.edit_mode:
                parent._push_undo()
            return original_handle(body)
        self._options_form.handle = _handle_with_undo

    def _snapshot_edit_state(self) -> dict:
        state = super()._snapshot_edit_state()
        if not self._has_reactive_options:
            state["__options"] = self._store.get(self.key, "__options")
        return state

    def _restore_edit_state(self, state: dict):
        super()._restore_edit_state(state)
        if not self._has_reactive_options and "__options" in state:
            self._store.set(self.key, "__options", state.get("__options"))

    @property
    def _current_options(self) -> list[str]:
        """The effective option list for the current render.

        For reactive options (SiblingBind), resolves from the sibling's current
        value. For literal options, reads the editable ListForm child's items.
        """
        if self._has_reactive_options:
            resolved = self._resolve_field("options")
            return list(resolved) if resolved else []
        return [item["value"] for item in self._options_form.items]

    @property
    def stale(self) -> bool:
        """True when the stored value is no longer in the current options."""
        return self.value is not None and self.value not in self._current_options

    @property
    def is_complete(self) -> bool:
        return self.value is not None and self.value in self._current_options

    def _serialize_state(self) -> dict:
        state = self._base_state() | {
            "value": self.value,
            "options": self._current_options,
        }
        if self._has_reactive_options:
            state["depends_on"] = self.options.key
        if self.stale:
            state["stale"] = True
        return state

    def get_affordances(self) -> list[Affordance]:
        opts = self._current_options
        affs: list[Affordance] = []
        if opts:
            opts_str = " | ".join(opts)
            affs.append(SelectAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": f"<{opts_str}>"},
                instruction=f"Select one of: {opts_str}.",
                options=opts,
                current=self.value if not self.stale else None,
            ))
        if self.stale:
            affs.append(SimpleButtonAffordance(
                label="Clear Selection",
                method="POST",
                url=self.url,
                body={"action": "clear"},
                instruction="Clear the stale selection.",
            ))
        return affs

    def render_from_data(self, data: dict) -> str:
        if self._has_reactive_options or not data.get("edit_mode"):
            options_html = ""
        else:
            options_html = self._options_form.render_safely()
        return render_template("choice.html", data=data, ef=self,
                               url=self.url, label=data["label"],
                               instruction=data.get("instruction") or "",
                               options_html=options_html)

    _actions = {None: "_do_set", "clear": "_do_clear"}

    def _do_set(self, body: dict) -> dict:
        value = body.get("value")
        if value in self._current_options:
            self._store.set(self._scope, self.key, value)
        else:
            return self._error(
                f"'{value}' is not a valid option.", body=body
            )
        return self.serialize()

    def _do_clear(self, body: dict) -> dict:
        self._store.set(self._scope, self.key, None)
        return self.serialize()
