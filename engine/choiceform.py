"""ChoiceForm — single selection from a list of options."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.affordances import Affordance
from engine.component import Component
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
    """Single selection from a fixed set of options."""
    form = "choice"

    options: list[str] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        from engine.listform import ListForm
        self._options_form = ListForm(
            key="__options",
            label="Options",
            allow_constraints=False,
        )

    @property
    def children(self) -> list[Component]:
        if self.edit_mode:
            return [self._options_form]
        return []

    def _bind_children(self, store, url_prefix):
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
        state["__options"] = self._store.get(self.key, "__options")
        return state

    def _restore_edit_state(self, state: dict):
        super()._restore_edit_state(state)
        self._store.set(self.key, "__options", state.get("__options"))

    @property
    def _effective_options(self) -> list[str]:
        """Read current options from the child ListForm."""
        return [item["value"] for item in self._options_form.items]

    @property
    def is_complete(self) -> bool:
        return self.value is not None and self.value in self._effective_options

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "value": self.value,
            "options": self._effective_options,
        }

    def get_affordances(self) -> list[Affordance]:
        opts = self._effective_options
        opts_str = " | ".join(opts)
        return [
            SelectAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={"value": f"<{opts_str}>"},
                instruction=f"Select one of: {opts_str}.",
                options=opts,
                current=self.value,
            )
        ]

    def render_from_data(self, data: dict) -> str:
        options_html = self._options_form.render_safely() if data.get("edit_mode") else ""
        return render_template("choice.html", data=data, ef=self,
                               url=self.url, label=data["label"],
                               instruction=data.get("instruction") or "",
                               options_html=options_html)

    def _handle(self, body: dict) -> dict:
        # Normal value setting
        value = body.get("value")
        if value in self._effective_options:
            self._store.set(self._scope, self.key, value)
        return self.serialize()
