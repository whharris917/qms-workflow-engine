# QMS Workflow Engine

A HATEOAS-driven form engine built on **eigenforms** — self-contained, self-rendering, self-sufficient units of interactive state. Each eigenform knows how to serialize itself to JSON, render itself to HTML, handle mutations, and report its own completeness.

## Quick Start

```bash
cd qms-workflow-engine
pip install flask markupsafe
python run.py
```

Open `http://127.0.0.1:5000` to see the page index.

## Architecture

```
run.py                  Entry point (Flask, threaded)
app/
  __init__.py           Flask app factory
  routes.py             Routes, SSE, content negotiation
  templates/            index.html, page.html (SSE client)
engine/                 Eigenform implementations
pages/                  Page definitions (auto-discovered)
data/                   Per-page JSON state files (created at runtime)
```

### Request Flow

| Method | URL | Behavior |
|--------|-----|----------|
| `GET /` | Page index |
| `GET /pages/{key}` | Page state (JSON or HTML via content negotiation) |
| `POST /pages/{key}` | Page-level action |
| `GET /pages/{key}/{path}` | Nested eigenform state |
| `POST /pages/{key}/{path}` | Mutate a nested eigenform |
| `GET /pages/{key}/stream` | SSE — pushes full page state on every mutation |

JSON is default. Browsers receive HTML (via `Accept: text/html`).

### Core Protocol

Every eigenform implements:

- **`serialize()`** — Canonical JSON: form type, key, label, value, completeness, affordances.
- **`render()`** — Calls `serialize()` then `render_from_data(data)`. HTML is a pure function of the serialized dict. Cannot drift.
- **`handle(action)`** — Processes a POST body and persists to store.
- **`is_complete`** — Whether this eigenform's data is sufficient.

Affordances are HATEOAS links: each carries `label`, `method`, `url`, `body` template, and `instruction`. Clients drive workflows entirely from the eigenform's own output.

### Key Design Patterns

- **Faithful Projection** — Hidden/collapsed eigenforms return `None` from `serialize()` and `""` from `render()`. JSON and HTML always agree.
- **Render-from-Serialize** — HTML derives from the serialized dict, never from internal state directly. Guarantees JSON/HTML consistency.
- **PageForm as Persistence Boundary** — Each PageForm creates its own Store (one JSON file per page). All children share it.
- **Stable IDs** — ListForm, TableForm, KeyValueForm, RepeaterForm use monotonic IDs that never shift on removal.
- **Batch Actions** — `{"action": "batch", "actions": [...]}` for atomic multi-step mutations.
- **Content Negotiation** — Single URL serves JSON (default) or HTML (browser).
- **N/A Escape Hatch** — CheckboxForm and ListForm support N/A mode for "none of these."

## Eigenform Reference

### Data Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **TextForm** | `engine/eigenforms.py` | Single free-form string input | Value is not None |
| **NumberForm** | `engine/number.py` | Numeric input with min/max/step/integer constraint | Value is not None |
| **DateForm** | `engine/date.py` | ISO 8601 date or datetime with optional bounds | Value is not None |
| **BooleanForm** | `engine/boolean.py` | Binary yes/no toggle with custom labels | Value is not None |
| **MemoForm** | `engine/memo.py` | Multi-line textarea with min/max length | Non-empty and meets min_length |
| **RatingForm** | `engine/rating.py` | Ordinal 1-N rating with optional per-value labels | Value is not None |
| **RangeForm** | `engine/range.py` | Slider over continuous range with optional unit | Value is not None |
| **ChoiceForm** | `engine/choice.py` | Single selection via radio buttons from fixed options | Valid option selected |
| **CheckboxForm** | `engine/eigenforms.py` | Multi-select with N/A mode | Any item checked or N/A |
| **MultiForm** | `engine/multi.py` | Groups FieldDescriptors under a single affordance | All fields filled |
| **ListForm** | `engine/listform.py` | Ordered list with add/edit/remove/reorder + N/A | Items > 0 or N/A |
| **TableForm** | `engine/table.py` | Dynamic columns + rows, inline cell editing | All cells filled |
| **RankForm** | `engine/rank.py` | Fixed-set item reordering with move up/down | User has submitted ordering |
| **KeyValueForm** | `engine/keyvalue.py` | Dynamic key-value pairs with stable entry IDs | At least one complete entry |

### Container Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **PageForm** | `engine/page.py` | Top-level container. Creates its own Store. Reset Page action. | All children complete |
| **TabForm** | `engine/tab.py` | Tabbed container. Only active tab in JSON/HTML. | All tabs complete |
| **ChainForm** | `engine/chain.py` | Sequential wizard. Auto-advances to first incomplete step. | All steps complete |
| **AccordionForm** | `engine/accordion.py` | Collapsible sections. Collapsed sections omitted from output. | All sections complete |
| **GroupForm** | `engine/group.py` | Named container for reusable compositions. Parameterizable via subclassing. | All children complete |
| **RepeaterForm** | `engine/repeater.py` | Stamps template eigenforms per dynamic entry. Compound scopes. | min_entries met and all entries complete |
| **SwitchForm** | `engine/switch.py` | Swaps between named alternative subtrees based on a sibling's value. | Active case complete (or no case active) |

### Conditional / Dynamic Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **VisibilityForm** | `engine/visibility.py` | Wraps a child with conditional visibility based on a sibling's value. | Always (if hidden) or delegates to child |
| **DynamicChoiceForm** | `engine/dynamic_choice.py` | Options computed from a sibling's value. Stale detection. | Valid option selected from current options |

### Sibling-Reading Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **ScoreForm** | `engine/score.py` | Read-only grading from answer key. Reads sibling values. | Always (read-only) |
| **ComputedForm** | `engine/computed.py` | Derived display from arbitrary compute function. Optional `store_result`. | Always (read-only) |
| **ValidationForm** | `engine/validation.py` | Cross-field validation rules. Pending/pass/fail. Can block page completion. | All rules pass (or `block_completion=False`) |

### Imperative Forms

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **ActionForm** | `engine/action.py` | Button with preconditions, optional two-step confirmation, side effects. | Always |

### Showcase

| Type | Module | Description | Complete When |
|------|--------|-------------|---------------|
| **RubiksCubeForm** | `engine/rubiks.py` | Full Rubik's Cube with face rotations, shuffle, restart. | Cube is solved |

## Defining a Page

Each `.py` file in `pages/` exports a `definition` — an unbound PageForm. The page key comes from the definition, not the filename.

```python
# pages/my_page.py
from engine.eigenforms import TextForm
from engine.page import PageForm

definition = PageForm(key="my-page", label="My Page", eigenforms=[
    TextForm(key="name", label="Your Name"),
])
```

Pages are auto-discovered at startup. No registration needed.

## Ordering Constraints

- **ComputedForm** with `store_result=True` must appear before any VisibilityForm that depends on its result (serialization is sequential).
- **DynamicChoiceForm** dependencies must appear before the DynamicChoiceForm itself.

## Demo Pages

| Page | Key | Description |
|------|-----|-------------|
| Page 1 | `page-1` | TextForm + CheckboxForm basics |
| Page 2 | `page-2` | TabForm with 3 tabs |
| Rubik's Cube | `page-3` | RubiksCubeForm showcase |
| Chain Wizard | `page-4` | ChainForm 4-step sequential |
| Table | `page-5` | TableForm with dynamic columns/rows |
| Change Request | `page-6` | MultiForm + ChoiceForm + CheckboxForm + ListForm |
| Math Test | `math-test` | Mixed eigenforms with ScoreForm grading |
| Upgraded Math Test | `upgraded-math-test` | All questions in outer ChainForm |
| Visibility Experiments | `visibility-experiments` | ChoiceForm controlling VisibilityForm children |
| Quiz Portal | `quiz-portal` | Nested TabForms with per-quiz ScoreForm |
| Vendor Assessment | `vendor-assessment` | All 23+ eigenform types, 3-level nesting, computed scores |
| Switch Demo | `switch-demo` | SwitchForm with ticket type driving BugReport/FeatureRequest/Question |
| Weird Experiments | `weird-experiments` | ValidationForm, DynamicChoiceForm, ActionForm, RepeaterForm |
