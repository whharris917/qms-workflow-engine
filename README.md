# QMS Workflow Engine

A compositional form engine built on **components** — self-contained, self-rendering, self-sufficient units of interactive state. Each component knows how to serialize itself to JSON, render itself to HTML, handle mutations, and report its own completeness. The engine powers the QMS (Quality Management System) for the Pipe Dream project.

## Quick Start

```bash
cd qms-workflow-engine
pip install flask markupsafe markdown pyyaml
python run.py
```

Open `http://127.0.0.1:5000` to see the home page.

## Site Structure

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home | Landing page with project overview |
| `/portal` | Agent Portal | Card grid of page types with instance management (create/open/delete) |
| `/qms` | QMS | Controlled document listing with stage badges |
| `/workspace` | Workspace | Active documents you're working on |
| `/inbox` | Inbox | Pending review and approval tasks |
| `/manual` | Quality Manual | Browsable QMS reference documentation (rendered from markdown) |
| `/readme` | README | This document |
| `/pages/{id}` | Component Page | A live page instance with full component rendering |

## Documentation

- **Conceptual primer and design plan**: served live at [`/framing`](http://127.0.0.1:5000/framing). Read this first if you are new to the engine — it walks through the core loop, defines the vocabulary (seed, Store, bind, descriptor, affordance), and maps component concepts onto their React equivalents.
- **Architecture reference**: [`docs/architecture.md`](docs/architecture.md). The authoritative reference for the load-bearing invariants — Props/State/Derived categories, keys and scope, reconciliation (including the callable-preservation limitation), affordance flotation, and the controlled/uncontrolled state boundary. Consult this before adding a new field, a new component type, or touching the reconciliation path.

## Architecture

```
run.py                  Entry point (Flask, debug, threaded)
app/
  __init__.py           Flask app factory
  routes.py             All routes, SSE, content negotiation
  registry.py           Instance registry (tracks spawned page instances)
  manual.py             Quality Manual markdown rendering helpers
  templates/
    base.html           Shared layout (dark sidebar nav)
    home.html           Landing page
    portal.html         Agent Portal (card grid)
    page.html           Component page wrapper (extends base, adds SSE + theme toggle)
    qms.html            QMS document dashboard
    workspace.html      Active document cards
    inbox.html          Review/approval queue (placeholder)
    manual_index.html   Quality Manual TOC
    manual_page.html    Quality Manual article viewer
    readme.html         README viewer
    components/         Per-type Jinja templates (one per component type)
    components/sleek/   Sleek theme overrides
  static/
    style.css           Default theme
    sleek.css           Sleek theme
    component.js        Client-side affordance delegation + SSE handling
engine/
  component.py          Base Component protocol
  pagecomponent.py           PageComponent (persistence boundary, structural mutations)
  store.py              JSON file store (one file per page, scoped by key)
  registry.py           Type registry (name -> class mapping, from_descriptor)
  templates.py          Jinja environment, theme resolution, render helpers
  affordances.py        Affordance data model (HATEOAS links)
  ...                   One module per component type
pages/                  Page definitions (auto-discovered, one .py file per page)
data/                   Per-page JSON state files + instance registry (created at runtime)
```

### API

| Method | URL | Behavior |
|--------|-----|----------|
| `GET /` | Home page (HTML) or seed/instance listing (JSON) |
| `GET /portal` | Agent Portal (HTML) or grouped seed/instance data (JSON) |
| `POST /instances` | Create a new page instance |
| `POST /instances/{id}/delete` | Delete a page instance |
| `GET /pages/{id}` | Page state (JSON or HTML via content negotiation) |
| `POST /pages/{id}` | Page-level mutation |
| `GET /pages/{id}/{path}` | Nested component state |
| `POST /pages/{id}/{path}` | Mutate a nested component |
| `GET /pages/{id}/stream` | SSE — pushes page state on every mutation |
| `GET /types` | Component type registry (JSON) |

JSON is the default response format. Browsers receive HTML via `Accept: text/html` content negotiation.

### Core Protocol

Every component implements:

- **`serialize()`** — Canonical JSON: form type, key, label, value, completeness, affordances.
- **`render()`** — Calls `serialize()` then `render_from_data(data)`. HTML is a pure function of the serialized dict.
- **`handle(action)`** — Processes a POST body and persists to store.
- **`is_complete`** — Whether this component's data is sufficient.

Affordances are HATEOAS links: each carries `label`, `method`, `url`, `body` template, and `instruction`. Clients drive workflows entirely from the component's own output.

### Key Design Patterns

- **Faithful Projection** — Hidden/collapsed components return `None` from `serialize()` and `""` from `render()`. JSON and HTML always agree.
- **Render-from-Serialize** — HTML derives from the serialized dict, never from internal state. Guarantees JSON/HTML consistency.
- **PageComponent as Persistence Boundary** — Each PageComponent creates its own Store (one JSON file). All children share it.
- **Stable IDs** — ListComponent, TableComponent, DictionaryComponent, RepeaterComponent use monotonic IDs that never shift on removal.
- **Batch Actions** — `{"action": "batch", "actions": [...]}` for atomic multi-step mutations.
- **Content Negotiation** — Single URL serves JSON (default) or HTML (browser).

## Component Types

26 unique component classes, registered under 31 names (5 aliases). NavigationComponent unifies four navigation modes and registers as `navigation`, `tab`, `chain`, `sequence`, and `accordion`. DictionaryComponent also registers as `keyvalue`.

### Data Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **TextComponent** | `engine/textcomponent.py` | Free-form string input. Single-line or multiline. | Non-empty (and meets min_length if set) |
| **NumberComponent** | `engine/numbercomponent.py` | Numeric input with min/max/step/integer constraint. Optional slider mode. | Value is not None |
| **DateComponent** | `engine/datecomponent.py` | ISO 8601 date or datetime with optional bounds. | Value is not None |
| **BooleanComponent** | `engine/booleancomponent.py` | Binary yes/no toggle with custom labels. | Value is not None |
| **ChoiceComponent** | `engine/choicecomponent.py` | Single selection via radio buttons from fixed options. | Valid option selected |
| **CheckboxComponent** | `engine/checkboxcomponent.py` | Multi-select with N/A mode. | Any item checked or N/A |
| **MultiComponent** | `engine/multicomponent.py` | Groups FieldDescriptors under a single affordance. | All fields filled |
| **ListComponent** | `engine/listcomponent.py` | Ordered list with add/edit/remove/reorder + N/A. Ordering constraints. | Items > 0 or N/A |
| **SetComponent** | `engine/setcomponent.py` | Unordered collection of unique items. Duplicates rejected. | Non-empty |
| **TableComponent** | `engine/tablecomponent.py` | Dynamic columns + rows, inline cell editing. Typed columns with component cells. | All cells filled |
| **DictionaryComponent** | `engine/dictionarycomponent.py` | Dynamic key-value pairs. Edit/remove by key, key rename. | At least one entry with key + value |
| **InfoComponent** | `engine/infocomponent.py` | Read-only text display. Always complete. Edit mode for content editing. | Always |

### Container Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **PageComponent** | `engine/pagecomponent.py` | Top-level container. Creates its own Store. Reset Page action. Optional `mutable_structure`. | All children complete |
| **NavigationComponent** | `engine/navigationcomponent.py` | Unified container with four modes: `tabs` (free access), `chain` (gated auto-advance), `sequence` (gated manual), `accordion` (expandable). | All children complete |
| **GroupComponent** | `engine/groupcomponent.py` | Named container for reusable compositions. Parameterizable via subclassing. | All children complete |
| **VisibilityComponent** | `engine/visibilitycomponent.py` | Wraps a child with conditional visibility based on a sibling's value. | Always (if hidden) or delegates to child |
| **RepeaterComponent** | `engine/repeatercomponent.py` | Stamps template components per dynamic entry. Compound scopes, stable IDs. | min_entries met and all entries complete |
| **SwitchComponent** | `engine/switchcomponent.py` | Swaps between named alternative subtrees based on a sibling's value. | Active case complete (or no case) |

### Sibling-Reading Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **ScoreComponent** | `engine/scorecomponent.py` | Read-only grading from answer key. Reads sibling values. | Always |
| **ComputedComponent** | `engine/computedcomponent.py` | Derived display from arbitrary compute function. Optional `store_result`. | Always |
| **ValidationComponent** | `engine/validationcomponent.py` | Cross-field validation rules. Pending/pass/fail. Can block page completion. | All rules pass (or `block_completion=False`) |

### Dynamic Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **DynamicChoiceComponent** | `engine/dynamicchoicecomponent.py` | Options computed from a sibling's value. Stale detection. | Valid option selected |
| **ActionComponent** | `engine/actioncomponent.py` | Button with preconditions, optional confirmation, side effects. Can return `structural_actions`. | Always |

### Wrapper Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **HistoryComponent** | `engine/historycomponent.py` | Wraps a component with append-only change history. Lazy detection on serialize. | Delegates to child |

### Runner Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **TableRunner** | `engine/tablerunner.py` | Reads a sibling TableComponent and presents rows as a gated sequential workflow. | All rows executed |

### Showcase

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **RubiksCubeComponent** | `engine/rubikscubecomponent.py` | Full Rubik's Cube with face rotations, shuffle, restart. | Cube is solved |

## Defining a Page

Each `.py` file in `pages/` exports a `definition` — an unbound PageComponent. Pages are auto-discovered at startup.

```python
# pages/my_page.py
from engine.textcomponent import TextComponent
from engine.pagecomponent import PageComponent

definition = PageComponent(key="my-page", label="My Page", components=[
    TextComponent(key="name", label="Your Name"),
])
```

## Themes

Two themes are available, toggled per-page via the toolbar:

- **Default** — Clean borders, supervisor-oriented layout.
- **Sleek** — Dark-accented theme with custom templates for NavigationComponent, GroupComponent, ListComponent, TableComponent, and TextComponent.

The theme is stored in a cookie (`c-theme`) and applied server-side via `before_request`. Jinja template resolution tries `components/sleek/{name}` first, falling back to `components/{name}`.

## Structural Persistence

Every component implements `to_descriptor()`, which serializes the tree structure (type, key, label, config, children) to a plain dict. `from_descriptor()` in the registry reconstructs the tree.

PageComponent uses this for structural persistence:

1. **First bind:** Serializes the seed components to a `__structure` key in the store.
2. **Subsequent binds:** Reads `__structure` from the store and reconstructs via `from_descriptor()`, matching against the seed to preserve callables.

The component tree structure survives server restarts. If the stored structure is corrupt, PageComponent falls back to the seed definition.

## Structural Mutations

Pages with `mutable_structure=True` expose affordances for runtime structure modification:

| Action | Description |
|--------|-------------|
| `add_component` | Insert a new component by type name + config. |
| `remove_component` | Remove a component and surgically clean its data from the store. |
| `move_component` | Reorder a component to a new position. |
| `rebuild_from_seed` | Discard all structural mutations and restore the original definition. |

**Self-modifying pages:** ActionComponent's `action_fn` can return `structural_actions` that PageComponent applies, enabling pages that reshape themselves in response to user interaction. Requires `mutable_structure=True`.

## Ordering Constraints

- **ComputedComponent** with `store_result=True` must appear before any VisibilityComponent that depends on its result (serialization is sequential).
- **DynamicChoiceComponent** dependencies must appear before the DynamicChoiceComponent itself.

## Component Type Registry

The registry (`engine/registry.py`) maps type name strings to component classes:

```python
from engine.registry import registry

registry.lookup("text")        # -> TextComponent
registry.lookup("navigation")  # -> NavigationComponent
registry.lookup("tab")         # -> NavigationComponent (alias)
registry.available()           # -> sorted list of all 31 registered names
```

Type names are derived by stripping the `Component` suffix and lowercasing (e.g., `TextComponent` -> `"text"`). GroupComponent subclasses register under their own names. All types are auto-registered on first access.
