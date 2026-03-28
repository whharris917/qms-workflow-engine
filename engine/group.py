"""GroupForm — a named container for reusable eigenform compositions.

The simplest container: holds children, renders them, has identity.
No collapse, no tabs, no sequencing. Just grouping with a name.

Use GroupForm to define reusable named compositions:

    # Define once
    address = GroupForm(key="address", label="Address", eigenforms=[
        TextForm(key="street", label="Street"),
        TextForm(key="city", label="City"),
        ChoiceForm(key="country", label="Country", options=["US", "UK", "DE"]),
    ])

    # Use in multiple pages
    PageForm(key="shipping", eigenforms=[address, ...])
    PageForm(key="billing", eigenforms=[address, ...])

For parameterized compositions, subclass GroupForm:

    class Address(GroupForm):
        def __init__(self, key: str, countries: list[str] = None):
            super().__init__(key=key, label="Address", eigenforms=[
                TextForm(key="street", label="Street"),
                TextForm(key="city", label="City"),
                ChoiceForm(key="country", label="Country",
                           options=countries or ["US", "UK", "DE"]),
            ])

    PageForm(key="page", eigenforms=[
        Address("home", countries=["US", "CA", "MX"]),
        Address("work"),
    ])

bind() deepcopies the GroupForm, so the same definition can safely
appear in multiple pages.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape

from engine.eigenforms import Eigenform
from engine.store import Store


@dataclass
class GroupForm(Eigenform):
    """A named group of eigenforms. The simplest container."""
    eigenforms: list[Eigenform] = field(default_factory=list)

    def to_descriptor(self) -> dict:
        desc = super().to_descriptor()
        desc["eigenforms"] = [ef.to_descriptor() for ef in self.eigenforms]
        return desc

    @property
    def children(self) -> list[Eigenform]:
        return self.eigenforms

    @property
    def is_complete(self) -> bool:
        return all(ef.is_complete for ef in self.eigenforms)

    def _bind_children(self, store: Store, url_prefix: str):
        self.eigenforms = [
            ef.bind(store=store, scope=self.key, url_prefix=f"{url_prefix}/{self.key}")
            for ef in self.eigenforms
        ]

    def _serialize_state(self) -> dict:
        return {
            "form": self.form,
            "key": self.key,
            "label": self.label,
            "instruction": self.instruction,
        }

    def serialize(self) -> dict:
        state = self._serialize_state()
        state["eigenforms"] = [s for ef in self.eigenforms if (s := ef.serialize()) is not None]
        state["complete"] = self.is_complete
        state["affordances"] = [a.serialize() for a in self.get_affordances()]
        return state

    def get_affordances(self):
        return []

    def render_from_data(self, data: dict) -> str:
        html = f'<h3>{escape(data["label"])}</h3>'
        if data.get("instruction"):
            html += f'<p>{escape(data["instruction"])}</p>'
        html += "".join(ef.render() for ef in self.eigenforms)
        return html

    def _handle(self, body: dict) -> dict:
        return self.serialize()
