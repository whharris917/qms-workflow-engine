"""Deep Dive — an honest, code-grounded analysis of what this engine actually is.

Self-referential by construction: this page is rendered by the engine it analyzes.
"""

from engine.infodisplay import InfoDisplay
from engine.navigation import Navigation
from engine.page import Page


_SECTION_1 = """\
Strip the marketing words. What remains?

A Python framework for defining interactive forms as data-class trees, persisted to per-instance JSON files. The form definition is a "seed"; binding it to a store produces a runtime instance. Each form — called a Component — is responsible for serializing its own state, rendering its own HTML, dispatching its own actions, and emitting "affordances" (the URLs and POST bodies the client can act on).

Containers (Page, Navigation, Group, Repeater) compose forms into trees. The composition is declarative; the runtime walks the tree to handle requests.

A more interesting characterization: this is a typed-tree DSL whose nodes are self-rendering, self-routing component instances, with a JSON descriptor as the on-disk representation and a chained "if action == ..." dispatch as the wire protocol.

It is not React. Not Django Forms. Not Streamlit. Closest analog: a server-rendered component tree where every component carries its own affordances instead of the page owning a routing table.

This page itself is one of those trees: a Page containing a Navigation in tabs mode, with InfoComponents holding the prose. The fact that this works at all — that a 600-word essay on the engine's architecture can be expressed as a composition of the engine's own primitives — is a non-trivial existence proof.
"""

_SECTION_2 = """\
The lifecycle in five steps.

1. Discover seeds. Files in pages/*.py export `definition = Page(...)`. `discover_pages()` reloads them on every request — effectively hot reload.

2. Bind. `seed.bind(data_dir, scope=instance_id)` deepcopies the seed, attaches it to a per-instance JSON store, and recursively binds children. The seed itself is never mutated; bindings are scoped instances.

3. Reconstruct from descriptor. If the parent's `__structure` exists in the store, the runtime tree is rebuilt from it via `from_descriptor`, with seed-matching to preserve callables that JSON cannot carry. The descriptor is the on-disk source of truth; the seed is the fallback for non-serializable behavior.

4. Handle action. A POST routes through `handle_action(path, body)` which walks the tree to find the target component, calls its `_handle()`, mutates the store, and optionally calls `_rebuild()` to refresh the live tree from the updated structure.

5. Serialize/render. Two-tier output: `_serialize_full()` produces the internal dict for HTML rendering; `serialize()` strips render-only noise for agent/JSON consumption.

This is well-defined, but it leaks complexity. The seed-match in step 3 exists because callables (lambdas in Computation.compute_fn, Action.action_fn, and any SiblingBind held in a reactive field) cannot round-trip through JSON. That is the structural limit of the descriptor-as-truth principle: it is true for scalar configuration, partial for behavior.
"""

_SECTION_3 = """\
Things this codebase gets right.

Clear separation of seeds and instances. Seeds are pure Python; instances are JSON files. Edit the seed and existing instances rebind to the new structure on the next request (with bounded drift).

Per-instance store files. Any worker can serve any instance — no in-memory page cache, no sticky sessions.

Atomic file writes. Recently fixed: `write_text` race conditions on Windows during Flask dev-reloader restarts now use write-temp-then-rename. Empty files are tolerated.

Descriptor as single source of truth. Recently completed: `__config`, `__label`, `__instruction` sidecar keys eliminated; the parent's `__structure` is the only place per-child seed-time fields live. `_set_my_field` and `_set_my_config` are the only sanctioned mutation paths. Legacy data auto-migrates on first bind.

Affordance flotation. Repeated affordances (Clear, Edit, Batch) bubble from any nesting depth to the Page level as parameterized compounds. About 60% reduction in affordance noise on flat pages, more on deep ones.

Clean module boundaries. `engine/` imports from neither `app/` nor `pages/`. No cycles. Containers and leaves share a single `Component` protocol with consistent overrides.

Two themes (default, sleek) via template-overlay. Sleek opts in by overriding individual templates and adds CSS; the engine itself does not know themes exist.

Parity test. `tests/test_parity.py` verifies that every affordance URL emitted in `serialize()` appears as a `data-c-*` attribute in the rendered HTML for all 18 pages. JSON-vs-HTML divergence is caught at CI time.
"""

_SECTION_4 = """\
What is this codebase clearly aspiring to?

Three signals are unmistakable.

First, HATEOAS-style affordances. Every component serializes its own URLs and POST bodies. The dream is that any client — human browser, AI agent, headless test runner — can read the page state and act on it without prior schema knowledge. The page is its own API.

Second, faithful projection. The JSON serialization is canonical; the HTML is a derivation. The parity test enforces that the two stay aligned. The implication: humans and agents see the same world.

Third, mutable structure. Pages with `mutable_structure=True` expose a builder UI and an action vocabulary (add_component, move_component, group_components, reparent_component, ungroup_component). Users — or agents — can edit the page tree at runtime. There is no separate "designer mode"; design and execution are the same surface with different affordances.

Combined: the codebase is aspiring to be a UI fabric where humans and AI agents share a uniform, self-describing protocol; where pages are first-class data; and where the line between "operator" and "developer" dissolves into runtime-mutable structure plus explicit affordances.

The supporting evidence is real. The Quiz Portal exists as a composition of seven component types and zero JavaScript. The Page Builder lets you assemble pages by drag-and-drop. The component-gallery page documents itself by rendering one of every type. None of this is mocked.
"""

_SECTION_5 = """\
Where the delta lives. Five honest gaps between ambition and delivery.

1. Action dispatch is unstructured. 88 `if action == ...` checks across 20 files. Page._handle alone has 11 elif branches. Adding a new action requires finding the right file, deciding undo policy, deciding rebuild policy, and wiring through `handle_action` path resolution. No registry, no decorator, no metadata. Adding the 30th action will continue this organic growth.

2. String-typed sibling references. Switch, Visibility, Computation, Validation, Action, and any component with a SiblingBind-valued field all reference siblings via a string key (directly as `depends_on="some_key"` or indirectly via `SiblingBind("some_key", fn)`). Delete the referenced sibling and dependents silently orphan. The self-describing protocol cannot describe its own inter-form dependencies. No validation, no warning, no graph.

3. No config-value validation. `_set_my_config("multiline", "abc")` writes a string into a boolean field and persists it. `validate_config()` (registry.py:180) checks field NAMES against dataclass fields but not value TYPES. The descriptor is truth, but nothing checks the truth's shape.

4. No concurrency model. Atomic at the file level, last-write-wins at the conceptual level. Two simultaneous POSTs to the same instance race: POST 1 reads state, POST 2 reads state, POST 1 writes, POST 2 writes — POST 1's mutation silently discarded. Fine for single-user; broken for collaboration.

5. Mutable structure is theme-coupled. The schematic builder UI exists only in `sleek/page.html`. Default theme has no visual editor. The most ambitious feature is gated behind a stylesheet choice rather than being a first-class engine capability.

None of these is a defect — they are all consequences of the codebase being honestly under construction. But the gap between "page as self-describing API" and "page that an arbitrary client can compose" is wider than the surface suggests.
"""

_SECTION_6 = """\
Code-quality findings, in descending order of weight.

Page: 1064 lines. TableForm: 1192 lines. Navigation: 665 lines. All three mix orchestration (bind, rebuild) with ad-hoc action dispatchers and tree-walking utilities. Splitting along the (orchestration, structural mutation, content mutation, rendering) axes would expose the actual coupling and probably reveal duplications.

Navigation is four classes in one. `mode in ("tabs", "chain", "sequence", "accordion")` switches not only display but also value shape (string for tabs/chain/sequence, dict for accordion), navigation rules, and completion semantics. The single-class implementation is DRY but the API surface is unclear; users must remember the mode is a personality dial. Either four subclasses or an explicit Strategy object.

Scope conventions are not consistent. Page: children share its `_scope`. Navigation and Group: children get `scope=self.key`. Repeater: `scope=self.key/entry_id`. Adding a new container type requires careful thought to avoid silent breakage. There is no `Scope` type and no architecture document explaining the convention.

`from_descriptor` cannot fully round-trip. Callables silently drop unless a matching seed is supplied. No warning, no typed nullable, no detection. Behavior loss is silent.

Migration cruft from the just-completed descriptor refactor lives in the bind hot path. `_migrate_legacy_overrides()` runs on every bind, doing store reads + descriptor walks + deletes. Once existing data is migrated (a finite event), this code is overhead with no value. Should be deleted with a kill-date comment.

Demo code in production palette. `RubiksCubeApp` (400 lines) and `TableRunner` ship in the registry alongside production primitives. They appear in the builder's type-picker. They belong in `engine/_examples/`.

`MultiForm`, `ListForm`, `Repeater` all express "multiple values" with different mechanisms. The distinctions are real but require explanation. Better naming or a documented sibling-relationship diagram would help.

Overall: the codebase is honest, modular, well-tested at the parity level, and visibly under active improvement. It is not the work of someone shipping the minimum; the descriptor-as-truth refactor (just completed) eliminated a real architectural smell at meaningful cost. The findings above are not "this is broken" — they are "this is what the next pass should clean up."
"""

_SECTION_7 = """\
Recommendations, prioritized for value-per-effort.

1. Action registry. Replace the 88 chained `if action == ...` checks with a per-class `_actions: dict[str, ActionSpec]` table where ActionSpec captures handler, undo policy, rebuild policy, edit-mode flag, and parameter validator. Inheritance handles base actions (clear, undo, set_mode, set_label, set_instruction). One-week refactor that pays back forever.

2. Architecture document. One page covering scope conventions, descriptor location, bind-time contract, and the seed-vs-descriptor relationship. Without it, the next contributor — human or AI — must read every container's `_bind_children` to understand the model.

3. Typed sibling references. Introduce a `SiblingRef` value type. At seed-construction time, validate the referenced sibling exists in the same scope. At delete time, refuse or warn if dependents exist. Closes the dependency-graph blind spot.

4. Validate config values, not just names. `_set_my_config` should consult the dataclass field annotation and reject mistyped values. Cheap, eliminates an entire class of silent corruption.

5. Split the megafiles. Page and TableForm partitioned by axis (binding / structural mutation / content mutation / rendering / dispatch). Surface the actual seams.

6. Promote mutable structure. Build the schematic editor in default theme, or move it from sleek/page.html into the engine. Right now the most novel feature is hidden behind a CSS choice.

7. Move demo forms out of the production registry. RubiksCubeApp and TableRunner go to `engine/_examples/` and stop appearing in builder type-pickers.

8. Delete `_migrate_legacy_overrides` with a kill-date comment. After all live instances have been bound at least once post-refactor, the migration is dead weight in the hot path.

The codebase is at the stage where the next round of improvements is no longer "make it work" but "make it clear." The architectural investment is real; the harvest is consistency, not capability. Prioritizing #1 and #3 above would have the largest second-order effect — they make every future addition easier and every existing piece safer.
"""


definition = Page(
    key="deepdive",
    label="Deep Dive: What This Actually Is",
    instruction="An honest, code-grounded analysis. Each tab is a section. Read in order or jump around.",
    components=[
        Navigation(
            key="sections",
            label="",
            mode="tabs",
            steps=[
                InfoDisplay(key="s1", label="1. What this is",
                         text=_SECTION_1),
                InfoDisplay(key="s2", label="2. The lifecycle",
                         text=_SECTION_2),
                InfoDisplay(key="s3", label="3. What works well",
                         text=_SECTION_3),
                InfoDisplay(key="s4", label="4. The aspiration",
                         text=_SECTION_4),
                InfoDisplay(key="s5", label="5. The delta",
                         text=_SECTION_5),
                InfoDisplay(key="s6", label="6. Code-quality audit",
                         text=_SECTION_6),
                InfoDisplay(key="s7", label="7. Recommendations",
                         text=_SECTION_7),
            ],
        ),
    ],
)
