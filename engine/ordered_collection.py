"""OrderedCollection — a reusable ordered-item engine with stable IDs and constraints.

This is a plain data structure, not an eigenform. It manages:
- Items with stable IDs, values, and a fixed flag
- A monotonic ID counter
- Static and dynamic must_follow ordering constraints
- Cycle detection and topological sort enforcement
- Constraint-aware move up/down

Eigenforms (ListForm, TableForm) compose this to get ordering logic
without duplicating it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OrderedCollection:
    """An ordered collection of items with stable IDs and ordering constraints.

    The collection operates on an internal state dict loaded via load().
    Mutation methods modify internal state and return it for the caller
    to persist.

    State dict shape:
        {"items": [{"id": "item_0", "value": "...", "fixed": True}, ...],
         "next_id": 3,
         "constraints": [{"item": "item_2", "after": "item_0"}, ...]}
    """
    id_prefix: str = "item"
    fixed_items: list[str] = field(default_factory=list)
    static_must_follow: dict[str, list[str]] = field(default_factory=dict)
    allow_constraints: bool = True

    def __post_init__(self):
        self._state: dict | None = None

    def load(self, state: dict | None) -> None:
        """Load a state snapshot. Called before each use."""
        self._state = state

    # --- Read properties ---

    @property
    def items(self) -> list[dict]:
        """Current item list. Seeds fixed_items on first access."""
        if self._state and isinstance(self._state, dict):
            return self._state.get("items", [])
        if self.fixed_items:
            return [{"id": f"{self.id_prefix}_{i}", "value": v, "fixed": True}
                    for i, v in enumerate(self.fixed_items)]
        return []

    @property
    def next_id(self) -> int:
        if self._state and isinstance(self._state, dict):
            return self._state.get("next_id", 0)
        if self.fixed_items:
            return len(self.fixed_items)
        return 0

    @property
    def item_ids(self) -> set[str]:
        return {i["id"] for i in self.items}

    @property
    def id_to_value(self) -> dict[str, str]:
        return {i["id"]: i["value"] for i in self.items}

    @property
    def stored_constraints(self) -> list[dict]:
        """Dynamic constraints from the store."""
        if self._state and isinstance(self._state, dict):
            return self._state.get("constraints", [])
        return []

    @property
    def effective_must_follow(self) -> dict[str, list[str]]:
        """Merge static must_follow with dynamic stored constraints."""
        result = {k: list(v) for k, v in self.static_must_follow.items()}
        for c in self.stored_constraints:
            result.setdefault(c["item"], [])
            if c["after"] not in result[c["item"]]:
                result[c["item"]].append(c["after"])
        return result

    # --- Query methods ---

    def can_move_up(self, idx: int, items: list[dict]) -> bool:
        """Check if moving item at idx up one position respects constraints."""
        if idx <= 0:
            return False
        mf = self.effective_must_follow
        moved_id = items[idx]["id"]
        displaced_id = items[idx - 1]["id"]
        if displaced_id in mf.get(moved_id, []):
            return False
        return True

    def can_move_down(self, idx: int, items: list[dict]) -> bool:
        """Check if moving item at idx down one position respects constraints."""
        if idx >= len(items) - 1:
            return False
        mf = self.effective_must_follow
        moved_id = items[idx]["id"]
        displaced_id = items[idx + 1]["id"]
        if moved_id in mf.get(displaced_id, []):
            return False
        return True

    def would_create_cycle(self, item_id: str, after_id: str,
                           mf: dict[str, list[str]]) -> bool:
        """Check if adding 'item must follow after' would create a cycle."""
        visited: set[str] = set()
        stack = [after_id]
        while stack:
            current = stack.pop()
            if current == item_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            stack.extend(mf.get(current, []))
        return False

    def enforce_constraints(self, items: list[dict]) -> list[dict]:
        """Reorder items to satisfy all constraints via stable topological sort."""
        mf = self.effective_must_follow
        if not mf:
            return items
        result: list[dict] = []
        deferred: list[dict] = []
        placed: set[str] = set()
        for item in items:
            prereqs = set(mf.get(item["id"], []))
            if prereqs <= placed:
                result.append(item)
                placed.add(item["id"])
                changed = True
                while changed:
                    changed = False
                    still_deferred = []
                    for d in deferred:
                        if set(mf.get(d["id"], [])) <= placed:
                            result.append(d)
                            placed.add(d["id"])
                            changed = True
                        else:
                            still_deferred.append(d)
                    deferred = still_deferred
            else:
                deferred.append(item)
        result.extend(deferred)
        return result

    # --- Internal helpers ---

    def _build_state(self, items: list[dict], next_id: int,
                     constraints: list[dict] | None = None) -> dict:
        """Build a state dict from components."""
        state = {"items": items, "next_id": next_id}
        if constraints:
            state["constraints"] = constraints
        self._state = state
        return state

    def _items_copy(self) -> tuple[list[dict], int, list[dict]]:
        """Return mutable copies of items, next_id, and constraints."""
        return (
            [dict(i) for i in self.items],
            self.next_id,
            list(self.stored_constraints),
        )

    # --- Mutation methods (raise ValueError on failure) ---

    def add(self, value: str) -> dict:
        """Add a new item. Returns new state."""
        items, next_id, constraints = self._items_copy()
        item_id = f"{self.id_prefix}_{next_id}"
        next_id += 1
        items.append({"id": item_id, "value": value})
        return self._build_state(items, next_id, constraints)

    def edit(self, item_id: str, value: str) -> dict:
        """Edit an item's value. Returns new state."""
        items, next_id, constraints = self._items_copy()
        ids = {i["id"] for i in items}
        if item_id not in ids:
            raise ValueError(f"Unknown item: {item_id}. Valid: {', '.join(ids)}")
        target = next(i for i in items if i["id"] == item_id)
        if target.get("fixed"):
            raise ValueError(f"Item {item_id} is fixed and cannot be edited.")
        target["value"] = value
        return self._build_state(items, next_id, constraints)

    def remove(self, item_id: str) -> dict:
        """Remove an item and clean up constraints. Returns new state."""
        items, next_id, constraints = self._items_copy()
        ids = {i["id"] for i in items}
        if item_id not in ids:
            raise ValueError(f"Unknown item: {item_id}. Valid: {', '.join(ids)}")
        target = next(i for i in items if i["id"] == item_id)
        if target.get("fixed"):
            raise ValueError(f"Item {item_id} is fixed and cannot be removed.")
        items = [i for i in items if i["id"] != item_id]
        constraints = [c for c in constraints
                       if c["item"] != item_id and c["after"] != item_id]
        return self._build_state(items, next_id, constraints)

    def move_up(self, item_id: str) -> dict:
        """Move an item up one position. Returns new state."""
        items, next_id, constraints = self._items_copy()
        ids = {i["id"] for i in items}
        if item_id not in ids:
            raise ValueError(f"Unknown item: {item_id}. Valid: {', '.join(ids)}")
        idx = next(i for i, it in enumerate(items) if it["id"] == item_id)
        if not self.can_move_up(idx, items):
            raise ValueError(f"Cannot move {item_id} up: at boundary or ordering constraint.")
        items[idx], items[idx - 1] = items[idx - 1], items[idx]
        return self._build_state(items, next_id, constraints)

    def move_down(self, item_id: str) -> dict:
        """Move an item down one position. Returns new state."""
        items, next_id, constraints = self._items_copy()
        ids = {i["id"] for i in items}
        if item_id not in ids:
            raise ValueError(f"Unknown item: {item_id}. Valid: {', '.join(ids)}")
        idx = next(i for i, it in enumerate(items) if it["id"] == item_id)
        if not self.can_move_down(idx, items):
            raise ValueError(f"Cannot move {item_id} down: at boundary or ordering constraint.")
        items[idx], items[idx + 1] = items[idx + 1], items[idx]
        return self._build_state(items, next_id, constraints)

    def move_to(self, item_id: str, position: int) -> dict:
        """Move an item to a specific position. Returns new state."""
        items, next_id, constraints = self._items_copy()
        ids = {i["id"] for i in items}
        if item_id not in ids:
            raise ValueError(f"Unknown item: {item_id}. Valid: {', '.join(ids)}")
        if not isinstance(position, int) or position < 0 or position >= len(items):
            raise ValueError(f"Invalid position: {position}. Valid: 0 to {len(items) - 1}")
        idx = next(i for i, it in enumerate(items) if it["id"] == item_id)
        item = items.pop(idx)
        items.insert(position, item)
        return self._build_state(items, next_id, constraints)

    def add_constraint(self, item_id: str, after_id: str) -> dict:
        """Add an ordering constraint and enforce it. Returns new state."""
        if not self.allow_constraints:
            raise ValueError("Ordering constraints are not allowed on this collection.")
        items, next_id, constraints = self._items_copy()
        ids = {i["id"] for i in items}
        if item_id not in ids:
            raise ValueError(f"Unknown item: {item_id!r}. Valid: {', '.join(ids)}")
        if after_id not in ids:
            raise ValueError(f"Unknown item: {after_id!r}. Valid: {', '.join(ids)}")
        if item_id == after_id:
            raise ValueError("An item cannot be constrained to follow itself.")
        mf = self.effective_must_follow
        if after_id in mf.get(item_id, []):
            raise ValueError(f"Constraint already exists: {item_id!r} must follow {after_id!r}.")
        if self.would_create_cycle(item_id, after_id, mf):
            raise ValueError(f"Would create a cycle: {after_id!r} transitively depends on {item_id!r}.")
        constraints = constraints + [{"item": item_id, "after": after_id}]
        state = self._build_state(items, next_id, constraints)
        # Re-enforce after adding constraint (may cascade reordering)
        items = self.enforce_constraints([dict(i) for i in self.items])
        return self._build_state(items, next_id, constraints)

    def remove_constraint(self, item_id: str, after_id: str) -> dict:
        """Remove a dynamic ordering constraint. Returns new state."""
        items, next_id, constraints = self._items_copy()
        new_constraints = [c for c in constraints
                           if not (c["item"] == item_id and c["after"] == after_id)]
        if len(new_constraints) == len(constraints):
            raise ValueError(f"No dynamic constraint: {item_id!r} after {after_id!r}.")
        return self._build_state(items, next_id, new_constraints)
