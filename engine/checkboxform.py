"""CheckboxForm — multi-select with explicit confirmation."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.affordances import Affordance, CheckboxAffordance, SimpleButtonAffordance
from engine.component import Component
from engine.templates import render_template


@dataclass
class CheckboxForm(Component):
    """Multi-select: a set of items, each independently selectable.

    Requires explicit confirmation via a "Done" action to be considered
    complete. This prevents premature auto-advance in ChainForm when
    the user has only checked one item but intends to check more.

    Done with no items checked means "none of these apply."
    Toggling any item after confirmation clears the confirmed state.
    """
    form = "checkbox"

    items: list[str] = field(default_factory=list)

    def __post_init__(self):
        super().__post_init__()
        from engine.listform import ListForm
        self._items_form = ListForm(
            key="__items",
            label="Items",
            allow_constraints=False,
        )

    @property
    def children(self) -> list[Component]:
        if self.edit_mode:
            return [self._items_form]
        return []

    def _bind_children(self, store, url_prefix):
        self._items_form = self._items_form.bind(
            store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
        # Seed initial items if no ListForm data exists yet
        if not self._items_form.value:
            for item in self.items:
                self._items_form.handle({"action": "add", "value": item})
        # Wrap child handle so CheckboxForm pushes undo before ListForm changes
        original_handle = self._items_form.handle
        parent = self
        def _handle_with_undo(body):
            if parent.edit_mode:
                parent._push_undo()
            return original_handle(body)
        self._items_form.handle = _handle_with_undo

    def _snapshot_edit_state(self) -> dict:
        state = super()._snapshot_edit_state()
        state["__items"] = self._store.get(self.key, "__items")
        return state

    def _restore_edit_state(self, state: dict):
        super()._restore_edit_state(state)
        self._store.set(self.key, "__items", state.get("__items"))

    @property
    def _effective_items(self) -> list[str]:
        """Read current items from the child ListForm."""
        return [item["value"] for item in self._items_form.items]

    @property
    def checked(self) -> dict[str, bool]:
        """Current state: {item: bool} for each item."""
        stored = self.value or {}
        return {item: stored.get(item, False) for item in self._effective_items}

    @property
    def confirmed(self) -> bool:
        """Whether the selection has been explicitly confirmed."""
        stored = self.value or {}
        return bool(stored.get("__confirmed"))

    @property
    def is_complete(self) -> bool:
        return self.confirmed

    def _serialize_state(self) -> dict:
        return self._base_state() | {
            "items": self.checked,
            "confirmed": self.confirmed,
        }

    def get_affordances(self) -> list[Affordance]:
        items = self._effective_items
        affs = [
            CheckboxAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={item: "<true | false>" for item in items},
                instruction="Set one or more items. Omitted items are unchanged. After setting, submit the 'Done' action to confirm.",
                items=self.checked,
            ),
        ]
        if not self.confirmed:
            affs.append(SimpleButtonAffordance(
                label="Done",
                method="POST",
                url=self.url,
                body={"action": "done"},
                instruction="Confirm the current selection (or none selected = none apply).",
            ))
        return affs

    def render_from_data(self, data: dict) -> str:
        items_html = self._items_form.render_safely() if data.get("edit_mode") else ""
        return render_template("checkbox.html", data=data, ef=self,
                               url=self.url, label=data["label"],
                               instruction=data.get("instruction") or "",
                               items_html=items_html)

    _actions = {
        None: "_do_toggle",
        "done": "_do_done",
    }

    def _do_toggle(self, body: dict) -> dict:
        current = self.checked
        changed = False
        for item_key, value in body.items():
            if item_key in current:
                current[item_key] = value
                changed = True
        if changed:
            current["__confirmed"] = False
        self._store.set(self._scope, self.key, current)
        return self.serialize()

    def _do_done(self, body: dict) -> dict:
        stored = dict(self.value or {})
        stored["__confirmed"] = True
        self._store.set(self._scope, self.key, stored)
        return self.serialize()
