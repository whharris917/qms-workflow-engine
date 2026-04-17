# QMS Workflow Engine

A compositional form engine built on **eigenforms** — self-contained, self-rendering, self-sufficient units of interactive state. Each eigenform knows how to serialize itself to JSON, render itself to HTML, handle mutations, and report its own completeness. The engine powers the QMS (Quality Management System) for the Pipe Dream project.

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
| `/pages/{id}` | Eigenform Page | A live page instance with full eigenform rendering |

## Documentation

- **Conceptual primer and design plan**: served live at [`/framing`](http://127.0.0.1:5000/framing). Read this first if you are new to the engine — it walks through the core loop, defines the vocabulary (seed, Store, bind, descriptor, affordance), and maps eigenform concepts onto their React equivalents.
- **Architecture reference**: [`docs/architecture.md`](docs/architecture.md). The authoritative reference for the load-bearing invariants — Props/State/Derived categories, keys and scope, reconciliation (including the callable-preservation limitation), affordance flotation, and the controlled/uncontrolled state boundary. Consult this before adding a new field, a new eigenform type, or touching the reconciliation path.

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
    page.html           Eigenform page wrapper (extends base, adds SSE + theme toggle)
    qms.html            QMS document dashboard
    workspace.html      Active document cards
    inbox.html          Review/approval queue (placeholder)
    manual_index.html   Quality Manual TOC
    manual_page.html    Quality Manual article viewer
    readme.html         README viewer
    eigenforms/         Per-type Jinja templates (one per eigenform type)
    eigenforms/sleek/   Sleek theme overrides
  static/
    style.css           Default theme
    sleek.css           Sleek theme
    eigenform.js        Client-side affordance delegation + SSE handling
engine/
  eigenform.py          Base Eigenform protocol
  pageform.py           PageForm (persistence boundary, structural mutations)
  store.py              JSON file store (one file per page, scoped by key)
  registry.py           Type registry (name -> class mapping, from_descriptor)
  templates.py          Jinja environment, theme resolution, render helpers
  affordances.py        Affordance data model (HATEOAS links)
  ...                   One module per eigenform type
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
| `GET /pages/{id}/{path}` | Nested eigenform state |
| `POST /pages/{id}/{path}` | Mutate a nested eigenform |
| `GET /pages/{id}/stream` | SSE — pushes page state on every mutation |
| `GET /types` | Eigenform type registry (JSON) |

JSON is the default response format. Browsers receive HTML via `Accept: text/html` content negotiation.

### Core Protocol

Every eigenform implements:

- **`serialize()`** — Canonical JSON: form type, key, label, value, completeness, affordances.
- **`render()`** — Calls `serialize()` then `render_from_data(data)`. HTML is a pure function of the serialized dict.
- **`handle(action)`** — Processes a POST body and persists to store.
- **`is_complete`** — Whether this eigenform's data is sufficient.

Affordances are HATEOAS links: each carries `label`, `method`, `url`, `body` template, and `instruction`. Clients drive workflows entirely from the eigenform's own output.

### Key Design Patterns

- **Faithful Projection** — Hidden/collapsed eigenforms return `None` from `serialize()` and `""` from `render()`. JSON and HTML always agree.
- **Render-from-Serialize** — HTML derives from the serialized dict, never from internal state. Guarantees JSON/HTML consistency.
- **PageForm as Persistence Boundary** — Each PageForm creates its own Store (one JSON file). All children share it.
- **Stable IDs** — ListForm, TableForm, DictionaryForm, RepeaterForm use monotonic IDs that never shift on removal.
- **Batch Actions** — `{"action": "batch", "actions": [...]}` for atomic multi-step mutations.
- **Content Negotiation** — Single URL serves JSON (default) or HTML (browser).

## Eigenform Types

26 unique eigenform classes, registered under 31 names (5 aliases). NavigationForm unifies four navigation modes and registers as `navigation`, `tab`, `chain`, `sequence`, and `accordion`. DictionaryForm also registers as `keyvalue`.

### Data Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **TextForm** | `engine/textform.py` | Free-form string input. Single-line or multiline. | Non-empty (and meets min_length if set) |
| **NumberForm** | `engine/numberform.py` | Numeric input with min/max/step/integer constraint. Optional slider mode. | Value is not None |
| **DateForm** | `engine/dateform.py` | ISO 8601 date or datetime with optional bounds. | Value is not None |
| **BooleanForm** | `engine/booleanform.py` | Binary yes/no toggle with custom labels. | Value is not None |
| **ChoiceForm** | `engine/choiceform.py` | Single selection via radio buttons from fixed options. | Valid option selected |
| **CheckboxForm** | `engine/checkboxform.py` | Multi-select with N/A mode. | Any item checked or N/A |
| **MultiForm** | `engine/multiform.py` | Groups FieldDescriptors under a single affordance. | All fields filled |
| **ListForm** | `engine/listform.py` | Ordered list with add/edit/remove/reorder + N/A. Ordering constraints. | Items > 0 or N/A |
| **SetForm** | `engine/setform.py` | Unordered collection of unique items. Duplicates rejected. | Non-empty |
| **TableForm** | `engine/tableform.py` | Dynamic columns + rows, inline cell editing. Typed columns with eigenform cells. | All cells filled |
| **DictionaryForm** | `engine/dictionaryform.py` | Dynamic key-value pairs. Edit/remove by key, key rename. | At least one entry with key + value |
| **InfoForm** | `engine/infoform.py` | Read-only text display. Always complete. Edit mode for content editing. | Always |

### Container Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **PageForm** | `engine/pageform.py` | Top-level container. Creates its own Store. Reset Page action. Optional `mutable_structure`. | All children complete |
| **NavigationForm** | `engine/navigationform.py` | Unified container with four modes: `tabs` (free access), `chain` (gated auto-advance), `sequence` (gated manual), `accordion` (expandable). | All children complete |
| **GroupForm** | `engine/groupform.py` | Named container for reusable compositions. Parameterizable via subclassing. | All children complete |
| **VisibilityForm** | `engine/visibilityform.py` | Wraps a child with conditional visibility based on a sibling's value. | Always (if hidden) or delegates to child |
| **RepeaterForm** | `engine/repeaterform.py` | Stamps template eigenforms per dynamic entry. Compound scopes, stable IDs. | min_entries met and all entries complete |
| **SwitchForm** | `engine/switchform.py` | Swaps between named alternative subtrees based on a sibling's value. | Active case complete (or no case) |

### Sibling-Reading Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **ScoreForm** | `engine/scoreform.py` | Read-only grading from answer key. Reads sibling values. | Always |
| **ComputedForm** | `engine/computedform.py` | Derived display from arbitrary compute function. Optional `store_result`. | Always |
| **ValidationForm** | `engine/validationform.py` | Cross-field validation rules. Pending/pass/fail. Can block page completion. | All rules pass (or `block_completion=False`) |

### Dynamic Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **DynamicChoiceForm** | `engine/dynamicchoiceform.py` | Options computed from a sibling's value. Stale detection. | Valid option selected |
| **ActionForm** | `engine/actionform.py` | Button with preconditions, optional confirmation, side effects. Can return `structural_actions`. | Always |

### Wrapper Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **HistoryForm** | `engine/historyform.py` | Wraps an eigenform with append-only change history. Lazy detection on serialize. | Delegates to child |

### Runner Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **TableRunner** | `engine/tablerunner.py` | Reads a sibling TableForm and presents rows as a gated sequential workflow. | All rows executed |

### Showcase

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **RubiksCubeForm** | `engine/rubikscubeform.py` | Full Rubik's Cube with face rotations, shuffle, restart. | Cube is solved |

## Defining a Page

Each `.py` file in `pages/` exports a `definition` — an unbound PageForm. Pages are auto-discovered at startup.

```python
# pages/my_page.py
from engine.textform import TextForm
from engine.pageform import PageForm

definition = PageForm(key="my-page", label="My Page", eigenforms=[
    TextForm(key="name", label="Your Name"),
])
```

## Themes

Two themes are available, toggled per-page via the toolbar:

- **Default** — Clean borders, supervisor-oriented layout.
- **Sleek** — Dark-accented theme with custom templates for NavigationForm, GroupForm, ListForm, TableForm, and TextForm.

The theme is stored in a cookie (`ef-theme`) and applied server-side via `before_request`. Jinja template resolution tries `eigenforms/sleek/{name}` first, falling back to `eigenforms/{name}`.

## Structural Persistence

Every eigenform implements `to_descriptor()`, which serializes the tree structure (type, key, label, config, children) to a plain dict. `from_descriptor()` in the registry reconstructs the tree.

PageForm uses this for structural persistence:

1. **First bind:** Serializes the seed eigenforms to a `__structure` key in the store.
2. **Subsequent binds:** Reads `__structure` from the store and reconstructs via `from_descriptor()`, matching against the seed to preserve callables.

The eigenform tree structure survives server restarts. If the stored structure is corrupt, PageForm falls back to the seed definition.

## Structural Mutations

Pages with `mutable_structure=True` expose affordances for runtime structure modification:

| Action | Description |
|--------|-------------|
| `add_eigenform` | Insert a new eigenform by type name + config. |
| `remove_eigenform` | Remove an eigenform and surgically clean its data from the store. |
| `move_eigenform` | Reorder an eigenform to a new position. |
| `rebuild_from_seed` | Discard all structural mutations and restore the original definition. |

**Self-modifying pages:** ActionForm's `action_fn` can return `structural_actions` that PageForm applies, enabling pages that reshape themselves in response to user interaction. Requires `mutable_structure=True`.

## Ordering Constraints

- **ComputedForm** with `store_result=True` must appear before any VisibilityForm that depends on its result (serialization is sequential).
- **DynamicChoiceForm** dependencies must appear before the DynamicChoiceForm itself.

## Eigenform Type Registry

The registry (`engine/registry.py`) maps type name strings to eigenform classes:

```python
from engine.registry import registry

registry.lookup("text")        # -> TextForm
registry.lookup("navigation")  # -> NavigationForm
registry.lookup("tab")         # -> NavigationForm (alias)
registry.available()           # -> sorted list of all 31 registered names
```

Type names are derived by stripping `Form` suffix and lowercasing (e.g., `TextForm` -> `"text"`). GroupForm subclasses register under their own names. All types are auto-registered on first access.
