from __future__ import annotations

from dataclasses import dataclass, field

from engine.affordances import Affordance, CheckboxAffordance, SimpleButtonAffordance
from engine.eigenform import Eigenform


@dataclass
class CheckboxForm(Eigenform):
    """Multi-select: a set of items, each independently selectable.

    Requires explicit confirmation via a "Done" action to be considered
    complete. This prevents premature auto-advance in ChainForm when
    the user has only checked one item but intends to check more.

    Done with no items checked means "none of these apply."
    Toggling any item after confirmation clears the confirmed state.
    """
    items: list[str] = field(default_factory=list)

    @property
    def checked(self) -> dict[str, bool]:
        """Current state: {item: bool} for each item."""
        stored = self.value or {}
        return {item: stored.get(item, False) for item in self.items}

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
        affs = [
            CheckboxAffordance(
                label=f"Set {self.label}",
                method="POST",
                url=self.url,
                body={item: "<true | false>" for item in self.items},
                instruction="Set one or more items. Omitted items are unchanged.",
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

    def _handle(self, body: dict) -> dict:
        action = body.get("action")
        if action == "done":
            stored = dict(self.value or {})
            stored["__confirmed"] = True
            self._store.set(self._scope, self.key, stored)
        else:
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
