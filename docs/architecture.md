# Component Engine — Architecture Reference

**Audience:** Engine contributors who want an authoritative reference for how
components, descriptors, Store state, and affordances relate to one another.
For a pedagogical introduction, see [`/framing`](../app/templates/framing.html)
or the project README.

This document defines the load-bearing invariants. If you are about to add a
field, introduce a new component type, change a routing convention, or touch
the reconciliation path, read the relevant section first.

---

## Table of Contents

1. [Categories of component data: Props, State, Derived](#1-categories-of-component-data)
2. [Keys and scope](#2-keys-and-scope)
3. [Reconciliation](#3-reconciliation)
4. [Affordance flotation (Portal)](#4-affordance-flotation-portal)
5. [Controlled vs uncontrolled state](#5-controlled-vs-uncontrolled-state)
6. [Vocabulary map](#6-vocabulary-map)

---

## 1. Categories of component data

**Every field on every component is one of three things.** Misplacing a field
into the wrong category is the single most common source of subtle bugs in
this engine. Know the category before you touch the field.

### 1.1 Props — live in the parent's `__structure` descriptor

A **prop** is a configuration value captured at seed-construction time,
overridable at runtime via the parent container's `__structure` descriptor
entry for this child.

**Canonical location:** the parent's Store at key `{parent_scope}.__structure`,
within the child's descriptor entry. The runtime component instance is a
*projection* of the descriptor, not an independent source.

**Mutation API:**
- `self._set_my_field(name, value)` — top-level descriptor fields (`label`,
  `instruction`, `editable`)
- `self._set_my_config(name, value)` — type-specific config entries (the
  `config` sub-dict of the descriptor)

Both helpers mutate the descriptor in place AND `setattr` on the runtime
instance so the live tree reflects the change before the next bind.

**Examples of props:**
| Component | Props |
|---|---|
| Base (all types) | `label`, `instruction`, `editable` |
| TextForm | `multiline`, `min_length`, `max_length` |
| NumberForm | `min_val`, `max_val`, `step`, `slider`, `unit` |
| BooleanForm | `true_label`, `false_label` |
| DateForm | `include_time`, `min_date`, `max_date` |
| Navigation | `mode`, `default_expanded` |
| DictionaryForm | `key_label`, `value_label` |
| MultiForm | `fields` (list of FieldDescriptor) |
| ListForm | `allow_constraints` |

**Rule:** If a field is declared in the component's `@dataclass` and its value
survives across requests because the container re-applies it on bind, it is a
prop.

### 1.2 State — lives in the Store at key scope

A **state** value is the mutable content a component owns directly.
Persisted per instance, per component key, in the per-instance JSON file.

**Canonical location:** the Store at entries keyed by the component's scope
(e.g., `hello/name.__value`, `page-2/tabs.__active`).

**Mutation API:** `self._handle(body)` — each component implements its own
action dispatch which reads the action, validates the parameters, writes to
the Store, and returns the updated state. Containers delegate via
`handle_action(path, body)` which walks the tree to the target child.

**Examples of state:**
| Component | State |
|---|---|
| TextForm | current text value |
| NumberForm | current number value |
| BooleanForm | current boolean value |
| ChoiceForm | current selected option |
| CheckboxForm | selected option set |
| Navigation | active tab / step / expanded sections |
| ListForm | ordered items |
| TableForm | cells, rows, columns, ordering constraints |
| DictionaryForm | key-value entries |

**Rule:** If a field's value changes because the *user did something*, it is
state.

### 1.3 Derived — computed on each serialize

A **derived** value is a pure function of the current prop+state pair
(possibly including siblings). Never persisted. Never mutated directly.
Recomputed every time `serialize()` or `render()` runs.

**Canonical location:** none. Computed on demand; discarded after the
response.

**Examples of derived:**
| Component | Derived |
|---|---|
| Base | `is_complete`, `has_data` |
| Computation | `compute_result` (from `compute(siblings)`) |
| Validation | rule pass/fail status |
| Score | score from answer-key comparison |
| DynamicChoiceForm | options (from `options_fn(siblings)`) |
| ListForm | `effective_must_follow` (constraints with fixed-demotion applied) |

**Rule:** If you can compute the value at serialize-time from other values,
it is derived. Don't cache it. Don't persist it. Recompute.

### 1.4 The invariant

> **Props live in the descriptor. State lives in the Store. Neither owns
> derived values.**

Every field addition must pick a category. The category determines:
- Where the value lives on disk
- Which mutation API to use
- Whether the field is reconstructed on reconciliation or not
- Whether the field survives a seed change

When in doubt, ask: *what changes this value?* Seed definitions → prop.
User actions → state. Other values → derived.

---

## 2. Keys and scope

### 2.1 Key

Every component has a `key: str` attribute set at construction. The key is
the component's **identity** within its containing scope.

**Rules:**
- Keys must be unique within a scope (enforced implicitly; collisions cause
  silent overwrite on bind).
- Keys are stable across reconciliation — they are how a descriptor entry
  matches against a seed entry.
- Keys are routable — they appear in URLs (`/pages/{id}/{path}` where `path`
  is a key-join).

Keys must be URL-safe. In practice: lowercase ASCII, hyphens and
underscores, no spaces. Enforcement is by convention, not validation (this
is one of the gaps on the typed-composition roadmap).

### 2.2 Scope

The **scope** is the namespace in which a key must be unique. Scope is
inherited from the nearest container.

**Scope-setting conventions (container-by-container):**

| Container | Child scope | Rationale |
|---|---|---|
| Page | `self.key` | Standardized in the stateless-server refactor |
| Navigation | `self.key` | Consistent with Page |
| Group | `self.key` | Consistent with Page |
| Repeater | `self.key/entry_id` | Compound scope for dynamic entries |
| TableForm (typed columns) | `table_key/row_id` | Compound scope per cell |

**The Page convention was aligned only in Session-2026-04-16-003.**
Previously Page wrote `__structure` at scope=binding-scope (instance ID)
but children bound at scope=self.key. That mismatch broke
`_get_my_descriptor()` lookups. If you are adding a new container type,
follow the Navigation/Group convention — do not re-introduce the
divergence.

### 2.3 Compound scopes

Some containers (Repeater, TableForm) emit children with compound
scopes like `my_repeater/entry-abc123`. The Store treats scopes as opaque
strings, so nesting works naturally — `my_repeater/entry-abc123/some-field`
is a valid Store key. Path-based URL routing mirrors the compound scope.

---

## 3. Reconciliation

The operation that rebuilds a live component tree from its persisted
representation is **reconciliation**. In React terms, this is what
`React.createElement` + the diffing step does between two render trees.

### 3.1 The `from_descriptor` function

Defined in `engine/registry.py` (also exposed as `reconcile` for
discoverability):

```python
def from_descriptor(desc: dict,
                    reg: ComponentRegistry | None = None,
                    seed: Component | None = None) -> Component
```

**Inputs:**
- `desc` — a descriptor dict (the JSON-serializable snapshot produced by
  `to_descriptor()`). Holds `type`, `key`, `label`, `instruction`,
  `editable`, optional `config`, and optional children fields.
- `reg` — the component type registry (defaults to the global registry).
- `seed` — the corresponding seed component, if available. Used to preserve
  callables.

**Output:** an unbound `Component` instance ready for `bind()`.

### 3.2 The algorithm

1. If the descriptor's `type` is a legacy container name (`tab`, `chain`,
   `sequence`, `accordion`), migrate in-flight to the unified
   `navigation` form with the appropriate `mode`.
2. If `seed is not None` and matches (same `form` and `key`):
   - `deepcopy(seed)` to produce the instance (preserves callables and
     other non-serializable fields).
   - Apply the descriptor's scalar fields onto the copy via
     `_apply_descriptor(desc)`. The descriptor wins over seed defaults —
     the descriptor is the canonical source of truth.
3. If seed is absent or does not match:
   - Look up the component class in the registry.
   - Construct a fresh instance from `key`, `label`, `instruction`,
     `editable`, and the `config` dict.
   - Recursively reconcile children.

### 3.3 The callable-preservation limitation

**The central tension:** JSON cannot round-trip functions. Any component
field that holds a callable (lambdas, validators, compute functions) must
be preserved through reconciliation via seed-match, because it cannot be
stored in the descriptor.

**Affected fields include:**
- `Computation.compute: Callable[[siblings], value]`
- `DynamicChoiceForm.options_fn: Callable[[siblings], list]`
- `Visibility.predicate: Callable[[siblings], bool]` (when callable)
- `Validation` rule predicates

**When the seed is missing or does not match** (e.g., the Python definition
moved, the key was renamed, a sibling was renamed), the fresh construction
path (step 3) cannot provide the callable. The component reconciles, binds,
and renders — but does nothing. No warning is emitted; no diagnostic is
visible in the UI.

**Mitigations today:** Page.bind() retains `_seed` and threads it into
all `from_descriptor` calls during `_rebuild`, so the seed is available
during the normal lifecycle. The gap manifests when: the seed is edited
between binds; a child is added via structural action with no matching seed
entry; or a descriptor is hand-constructed.

**Planned (Pass 2 of the framing design plan):** when a type declares
callable-valued fields, require the `seed` parameter. Return a typed
diagnostic (not `None`) when seed-match fails so broken reconciliation is
visible in the UI rather than silent.

### 3.4 What reconciliation does NOT do

- **Does not walk into the bound runtime.** Reconciliation produces an
  *unbound* tree. Bind is a separate step.
- **Does not validate descriptor shape.** If a descriptor has an unknown
  key, a wrong type, or mis-shaped children, reconciliation will either
  fail loudly (unknown type) or silently accept (wrong field types). Field
  shape validation is queued for Pass 2.
- **Does not diff two descriptors.** Unlike React's reconciliation (which
  diffs old vs new render trees), this operation reconciles *one*
  descriptor against a seed. Descriptor diffing is not a concept here
  because the store is the only source of truth.

---

## 4. Affordance flotation (Portal)

**Affordance flotation** is the engine's equivalent of a React Portal: a
mechanism for a deeply-nested child's affordance to surface at the Page
level in the agent-facing JSON, rather than being rendered where the child
lives.

### 4.1 Motivation

An agent consuming the page's JSON needs to know what actions exist. If a
page has 20 children and each child has a `Clear` affordance, a naive
serialization emits 20 identical `Clear` affordances (one per child). The
agent must parse all 20 to learn that "Clear" exists.

Flotation collapses these: one parameterized `Clear` affordance at the
Page level, carrying a `targets` dict mapping full URLs to child
labels. The agent sees one action; the 20 sites remain addressable by URL.

### 4.2 What gets floated

An affordance floats up if it carries a `_floatable: str` marker. The
string identifies the merge group — affordances sharing the same marker
collapse together. Current floatable markers:

- `clear` — the universal Clear affordance (emitted by every data
  component with `has_data = True`)
- `edit` — the `set_mode` affordance (emitted on every editable component)
- `batch` — the Batch affordance (emitted on every container)

### 4.3 How flotation works

1. Each component's `_serialize_full()` tags its floatable affordances with
   `_floatable = "<marker>"` on the serialized dict.
2. Page's `_collect_floatable()` recursively walks `component`,
   `components`, `sections`, `steps`, and similar child fields, collecting
   floatable affordances from any depth.
3. Page strips the floated affordances from child serializations.
4. Page groups the collected affordances by merge marker and emits one
   parameterized compound affordance per group, with a structured `targets`
   dict: `{full_url: child_label}`.

### 4.4 What flotation is NOT

- **Not applied to HTML rendering.** The human UI still renders per-child
  affordances where they live — deep-nested Clear buttons appear at the
  data component. Flotation is an agent-facing optimization only.
- **Not a visibility mechanism.** A non-floatable affordance stays where
  it is; flotation is purely additive for floatable ones.
- **Not a replacement for explicit routing.** Floated affordances still
  target specific URLs; the agent posts to `targets[url]` not to the
  compound affordance's URL directly.

### 4.5 Adding a new floatable affordance type

1. In the emitting component's `_serialize_full()`, set
   `affordance._floatable = "<unique-marker>"` on the affordance object
   before it is serialized.
2. In Page's compound-affordance generation, register a template for
   the new marker (label, body shape, instruction).
3. No changes needed in the recursive walker — it uses only the
   `_floatable` marker presence.

---

## 5. Controlled vs uncontrolled state

Two distinct axes of state ownership operate in this engine. Confusing them
causes cross-boundary bugs.

### 5.1 Controlled state — server-owned

**Owned by the server.** Lives in the Store. Round-trips through
serialization. Present identically in JSON and HTML responses.

Controlled state includes:
- All form values (TextForm text, NumberForm number, ChoiceForm selection)
- Container navigation state (active tab, open sections)
- Structural configuration (descriptor entries)
- Completion status (derived, but server-computed)

Controlled state changes only through the Handle step of the core loop: a
POST with an action, processed by `_handle()`, written to the Store.

### 5.2 Uncontrolled state — client-owned

**Owned by the browser.** Never touches the server. Present in neither
JSON nor the HTML markup — lives in the DOM and JS runtime.

Uncontrolled state includes:
- Input focus
- Scroll position (window and nested)
- `<details>` open/closed state (where purely ornamental)
- CSS transitions in progress
- Text entered into an input but not yet submitted
- Drag-in-progress coordinates
- Ephemeral tooltips, hover states

Uncontrolled state is preserved across POST responses by **morphdom**. The
`onBeforeElUpdated` hook in `app/static/component.js` skips morphing
elements that currently have focus, so a user mid-typing is never
disturbed. The rest of the uncontrolled state survives by virtue of
morphdom mutating only changed subtrees.

### 5.3 The boundary

| Question | Answer |
|---|---|
| Can an agent observe this value? | If yes → controlled. |
| Does this value survive a page reload? | If yes → controlled. |
| Is this value in the JSON response? | If yes → controlled. |
| Does a human care if this value resets? | If yes AND it doesn't survive reload → it was uncontrolled and shouldn't have been. |

### 5.4 When you are tempted to violate the boundary

If you find yourself wanting to store scroll position in the Store, or
wanting to persist focus across requests: stop. The value is uncontrolled
by design. Morphdom handles it. Pushing it server-side breaks the agent
contract (agents don't have scrollbars) and introduces state that has no
right to be there.

The reverse also applies: if you find yourself wanting to cache the
current text value in JS so it survives a page reload, stop. The value is
controlled. Submit it. Let the server own it.

---

## 6. Vocabulary map

A cross-reference between this codebase's terms and the equivalent React
terms, for contributors arriving with a React background. The base class
is named `Component` intentionally — the shared vocabulary is the point.
The table below covers the less-obvious alignments.

| This codebase | React | Notes |
|---|---|---|
| Seed constructor args | Props | Captured in the `__structure` descriptor. |
| Store entry at key scope | `useState` | Server-persisted. |
| `is_complete`, `effective_*`, `compute()` | Derived state | Recomputed each serialize. |
| `__structure` descriptor | Element tree / JSX output | Serializable. |
| `from_descriptor()` / `reconcile()` | Reconciliation | See §3. |
| `Component.key` | Component key | Identity across reconciliation. |
| `components=[...]`, `steps=[...]` | `children` prop | Container-specific names. |
| `render()` + Jinja2 templates | `render()` | Theme-fallback resolution. |
| `morphdom` (`_cSwap` in component.js) | Virtual DOM diff | Client-side, in-place. |
| Affordance flotation | Portal (novel variant) | Agent-JSON-only; see §4. |
| Faithful projection | Controlled/uncontrolled boundary | See §5. |
| `onBeforeElUpdated` hook | `ref` for focus preservation | Same mechanism. |
| Fragment | Group with no decoration | Implicit. |

**Concepts this codebase does NOT have (by design):**

| React concept | Why absent |
|---|---|
| Hooks (`useState` etc.) | Python closure ergonomics don't support the model. Component subclasses cover composable state. |
| Functional components | Without hooks, no composition benefit. |
| JSX | Seed files are our JSX — Python is more honest. |
| Refs (imperative DOM escape hatch) | Would break HATEOAS and replayability. |
| Suspense / Server Components | Solve client-side hydration problems we don't have. |
| Context | Not yet wanted — parked until a concrete pain point. |
| Error boundaries | Planned (Pass 3 of the framing design plan). |

See [`/framing`](../app/templates/framing.html) §7 for the full rationale on
non-borrowings and §8 for the roadmap.

---

## Change log

- Session-2026-04-18-001: Class taxonomy refactor — the flat `*Component` suffix replaced with role-specific suffixes. Forms (`*Form`) produce State: TextForm, NumberForm, etc. Containers are unsuffixed nouns: Page, Navigation, Group, Repeater, Switch, Visibility. Derivations are standalone nouns: Computation, Score, Validation. Display: InfoDisplay. Imperative: Action. Wrapper: Historizer. App: RubiksCubeApp. Runner: TableRunner (unchanged). Module files renamed to match (`engine/textform.py`, `engine/page.py`, `engine/computation.py`, etc.). The `form` property on Component replaced with an explicit class attribute on every subclass — registry type names (e.g., `"text"`, `"page"`, `"computed"`) are now declared, not derived. Note: `*Form` was previously used in Session-2026-03-25-001 as a universal suffix meaning "self-contained component" (every class was a Form, so Form meant nothing). This reintroduction is narrower: `*Form` now means specifically "data-entry widget," one of eight distinct categories. Not a reversion — a refinement.
- Session-2026-04-17-002: `Eigenform` base class and all `*Form` subclasses renamed to `Component` / `*Component`. The `eigenforms/` template directory, `eigenform.js` static asset, and all `ef-*` / `data-ef-*` CSS/DOM prefixes renamed to `c-*` / `data-c-*`. Module files renamed to match (`engine/*component.py`). Registry type-name derivation now strips the `Component` suffix. Rationale: the custom name obscured that the base class is, by design, a plain component in the React sense — keeping the unfamiliar word was sunk cost, not a carrier of the actual invariant.
- Session-2026-04-17-001: initial draft. Pass 1 of the framing design plan.
- Session-2026-04-17-001: Pass 3 of the framing design plan landed.
  - `Component.render_safely()` — default method wraps `render()` in try/except and returns a structured error card on failure. Containers iterate children via `render_safely()` instead of `render()` — 18 call sites across 10 component modules swapped.
  - `engine/component.py::_render_error_card(ef, exc)` — the error-card renderer. Detects Flask debug mode to optionally include a traceback. Falls back to a minimal inline HTML card if the template itself fails, so nothing can make a page unviewable.
  - `app/templates/components/_error_boundary.html` — the card template: error badge, component type, key, exception class, message, optional collapsible traceback, sibling-continuity hint.
  - `app/static/style.css` — theme-agnostic `.c-error-*` classes (red/amber palette, monospace exception details).
  - Scope deliberately excluded from Pass 3: `serialize_safely()` for JSON parity; `bind()` and `_handle()` error scoping. Bind errors have no in-place representation (the component tree literally does not exist post-bind-failure), so those remain 500s for now. Parked for a future pass.
- Session-2026-04-17-001: Pass 2 of the framing design plan landed.
  - `engine/sibling_ref.py` — `SiblingRef` str-subclass value type. Seven sibling-reading components (Switch, Visibility, DynamicChoiceForm, Computation, Action, Validation, Score) coerce their `depends_on` fields into `SiblingRef` at construction.
  - `Page._validate_sibling_refs()` — walks the bound tree after bind, builds a scope map, and validates every SiblingRef resolves. Raises `SiblingRefError` with actionable diagnostics on stale or type-mismatched refs.
  - `engine/component.py::_validate_field_value` — field-type validation at the `_set_my_field` / `_set_my_config` boundary. Supports simple types, `X | None` / Union, `Literal[...]`, and is permissive on complex/unknown annotations.
  - `Navigation.mode: Literal["tabs","chain","sequence","accordion"]` and `FieldDescriptor.type: Literal["text","choice"]` — enum-like fields now validated at the boundary by Move 2.
