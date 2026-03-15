# Unified Workflow Engine

The runtime that interprets YAML workflow definitions and drives agent interaction through the Agent Portal. Any workflow — from simple field-based forms to complex branching processes with evidence tables — can be built entirely in YAML. No Python code is required for new workflows.

---

## Architecture

```
                    YAML Definition
                         |
                    +-----------+
                    |  Runtime  |    runtime/__init__.py (WorkflowRuntime)
                    +-----------+
                   /    |    |    \
              schema  eval  render  actions
                |       |     |       |
            Parse    Gates  Page    Mutations
            YAML    Visibility Dict   State
                    Acceptance       Changes
```

**The runtime** (`runtime/`) is the single engine that replaces four former handler modules. It loads a YAML definition, parses it into typed dataclasses, and implements the handler protocol that `app.py` consumes.

**The handler protocol** is unchanged — every workflow (built-in or custom) exposes:
- `default_data()` — initial state dict
- `render_node(data, workflow_id)` — page dict with `{state, instructions, affordances}`
- `process_action(data, workflow_id, body)` — mutate state, return rendered page or error
- `resolve_resource(resource, body)` — translate URL segment to internal action

**The infrastructure** (`app.py`, `templates/`, SSE, feedback diffing, state persistence) is workflow-agnostic and unchanged.

---

## Content Primitives

Three types of content can appear in any workflow node. They can be mixed freely within a single workflow — a node can have fields alongside a table, or fields alongside a list.

### Fields

Named, typed values. The fundamental unit of data collection.

```yaml
fields:
  title:
    label: Document Title
    type: text          # text | boolean | select | computed
    key: title
    instruction: "A short, descriptive title."
    default: null
```

**Field types:**

| Type | Description | Agent interaction |
|------|-------------|-------------------|
| `text` | Free-form string | Agent provides any string value |
| `boolean` | True/false | Agent selects true or false |
| `select` | Constrained choice | Agent picks from a predefined list |
| `computed` | Read-only, evaluated by the engine | No affordance generated |

**Field properties:**

| Property | Purpose |
|----------|---------|
| `key` | Machine-readable state key (unique across workflow) |
| `label` | Human-readable name shown in UI |
| `instruction` | Guidance text shown alongside the field |
| `default` | Initial value (typically null) |
| `options` | For select: inline list of valid choices |
| `options_from` | For select: reference to a top-level `option_sets` entry |
| `dynamic_options` | For select: options that change based on another field's value |
| `visible_when` | Condition dict: field is hidden (and affordance suppressed) when false |
| `side_effects` | When a condition is met after setting this field, auto-set other fields |
| `compute` | For computed: expression that produces the field's value |

### Tables

Two-dimensional structures with typed columns and rows. Tables have a construction phase (building the structure) and an optional execution phase (filling cells at runtime with an integrated engine).

```yaml
table:
  column_type_catalog: column_types   # reference to top-level catalog
  properties:
    sequential_execution: {type: boolean, default: false}
  operations: [add_column, remove_column, rename_column, set_column_type,
               add_row, remove_row, set_cell, set_choices, set_rule,
               set_prerequisites, set_property]
```

**Column types** are classified by when they get filled:

| Category | Prefix | Filled During | Types |
|----------|--------|---------------|-------|
| Non-executable | `ne-` | Construction | `ne-free-text`, `ne-prerequisite` |
| Executable | `ex-` | Execution | `ex-free-text`, `ex-choice-list`, `ex-cross-reference`, `ex-signature` |
| Auto-executed | `ae-` | Automatically | `ae-acceptance-criteria` |

**Execution** is enabled by setting `execution: true` on a node. The runtime delegates to the `engine/` package (PlanEngine) which computes cell states, gating, sequential locking, cascade revert, and acceptance criteria evaluation.

**Cell operations** during execution: `fill`, `sign`, `mark_na`, `initiate_issue`.

### Lists

Ordered collections with structural editing operations. Each item conforms to a schema.

```yaml
lists:
  findings:
    label: Finding
    item_schema:
      title: {type: text, required: true}
      severity: {type: select, options: [Low, Medium, High]}
    operations: [add, edit, remove, reorder]
    focus: true    # enables focused-item pattern
```

**Operations:** `add`, `edit`, `remove`, `reorder`. When `focus: true`, a `list_select` affordance lets the agent set a focused item.

**State:** Stored as an array in the workflow data dict. Rendered generically by the observer's `wfRenderStateProps`.

---

## Expression Language

All conditions — gates, visibility, acceptance criteria, navigation guards — use the same expression tree schema.

### Leaf conditions

```yaml
{type: field_truthy, key: title}              # data[key] is truthy
{type: field_equals, key: status, value: X}   # data[key] == X
{type: field_not_null, key: title}            # data[key] is not None
{type: table_has_columns}                     # table has >= 1 column
{type: table_has_rows}                        # table has >= 1 row
{type: set_membership, key: X, set_ref: Y}   # data[X] in option_sets[Y]

# Acceptance-criteria leaves (delegated to engine/criteria.py):
{type: all-executed}                          # all executable columns filled
{type: column, column: 2, operator: is-filled}
{type: column, column: 3, operator: equals, value: Pass}
```

### Composite conditions

```yaml
{op: AND, conditions: [...]}    # all must pass
{op: OR, conditions: [...]}     # at least one must pass
{op: NOT, conditions: [...]}    # first condition inverted
```

### Where expressions are used

| Context | YAML key | Effect when false |
|---------|----------|-------------------|
| Field visibility | `visible_when` | Field hidden, affordance suppressed |
| Proceed gate | `proceed.gate` | Proceed affordance suppressed |
| Navigation guard | `navigation[].when` | Navigation affordance suppressed |
| Side effect trigger | `side_effects[].when` | Side effect does not fire |
| Acceptance criteria | Column `rule` | Row does not pass acceptance |

---

## Navigation

### Sequential

- **proceed** — advance to the next node in declaration order (or to a specified `target` node)
- **go_back** — return to the previous node

### Random access

- **go_to** — jump to any named node

### Terminal

- **submit** — mark current node complete and advance (initializes execution engine if next node has `execution: true`)
- **restart** — reset to initial state

### Conditional navigation

Navigation entries accept a `when` expression. If the condition evaluates false, the affordance is suppressed:

```yaml
navigation:
  - action: go_to
    node: escalation
    label: Escalate
    when: {type: field_equals, key: severity, value: Critical}
```

### Proceed with target (branching)

Proceed can jump to a non-sequential node:

```yaml
proceed:
  label: Finish
  target: done    # jump to 'done' instead of next sequential node
  gate: {type: field_truthy, key: resolution}
```

This enables diamond-shaped workflows where multiple paths converge.

---

## Inter-Field Dependencies

### Dynamic options

A select field's options can depend on another field's current value:

```yaml
affected_system:
  label: Affected System
  type: select
  key: affected_system
  dynamic_options:
    source_key: category
    mapping:
      Infrastructure: [Network, DNS, Load Balancer]
      Application: [API Gateway, Auth Service, Frontend]
    default: []
```

When `category` changes, `affected_system`'s available options update automatically. Validation enforces the current option set.

### Side effects

When a field is set and a condition is met, other fields can be auto-populated:

```yaml
severity:
  label: Severity
  type: select
  key: severity
  options: [Critical, High, Medium, Low]
  side_effects:
    - when: {type: field_equals, key: severity, value: Low}
      set: {needs_investigation: false}
    - when: {type: field_equals, key: severity, value: Critical}
      set: {needs_investigation: true, priority: urgent}
```

Side effects fire immediately after the field is set, before the page is re-rendered.

---

## YAML Schema Reference

A complete workflow definition:

```yaml
# Identity
workflow_title: My Workflow
workflow_description: One-line summary.

# Lifecycle
lifecycle_banner: [Phase 1, Phase 2, Phase 3]

# Shared data (optional)
option_sets:
  categories: [A, B, C]
  subcategories_a: [A1, A2]

# Column type catalog (optional, for table workflows)
column_types:
  ne-free-text: {label: Free Text, category: non-executable, description: "..."}
  ex-choice-list: {label: Choice List, category: executable, description: "..."}
  ae-acceptance-criteria: {label: Acceptance, category: auto-executed, description: "..."}

# Nodes
nodes:
  step_one:
    title: Step One
    lifecycle_label: Phase 1
    instruction: "What to do at this step."
    show_all_fields: false          # true = show fields from all nodes

    # Content: fields
    fields:
      my_field:
        label: My Field
        type: text
        key: my_field
        instruction: "Guidance text."
        default: null
        visible_when: {other_field: true}
        side_effects:
          - when: {type: field_equals, key: my_field, value: X}
            set: {derived_field: Y}

    # Content: lists
    lists:
      my_list:
        label: Item
        item_schema:
          name: {type: text, required: true}
          status: {type: select, options: [Active, Inactive]}
        operations: [add, edit, remove, reorder]
        focus: true

    # Content: table
    table:
      column_type_catalog: column_types
      properties:
        sequential_execution: {type: boolean, default: false}
      operations: [add_column, add_row, set_cell, ...]

    # Execution engine (table required)
    execution: false

    # Navigation
    navigation:
      - action: go_back
        label: Go back
      - action: go_to
        node: other_step
        label: Jump to Other
        when: {type: field_equals, key: mode, value: advanced}

    # Proceed gate
    proceed:
      label: Continue
      gate: {op: AND, conditions: [{type: field_truthy, key: my_field}]}
      target: step_three        # optional: non-sequential jump

    # Terminal actions
    actions:
      - action: submit
        label: Submit
      - action: restart
        label: Start Over
```

---

## Affordance Generation

Affordances are **derived from content + state**, not declared. The runtime generates them in this order:

1. **Field affordances** — for each visible, non-computed field: `"Set {label} (current: {value})"`
2. **List affordances** — for each list: add, select, edit, remove, reorder (based on declared operations)
3. **Navigation affordances** — for each navigation entry whose `when` condition passes
4. **Proceed affordance** — if the proceed gate evaluates to true
5. **Node action affordances** — submit, restart (unconditional)
6. **Table structural affordances** — add_column, set_cell, etc. (based on declared operations)
7. **Execution affordances** — cell operations from `engine.get_plan_state().next_actions`
8. **Execution complete affordance** — when all acceptance criteria pass

Each affordance includes: `id`, `label`, `method` (POST), `url`, `body`, and optional `parameters` with `options`/`labels` for constrained choices.

---

## File Structure

```
wfe-ui/
  runtime/
    __init__.py        WorkflowRuntime class — the single entry point
    schema.py          Dataclasses: WorkflowDef, NodeDef, FieldDef, ListDef, etc.
    evaluator.py       Unified expression evaluator
    renderer.py        Page dict builder + affordance generation
    actions.py         Action dispatcher (fields, lists, tables, navigation, execution)
    compat.py          Normalizes old YAML formats to canonical schema
  engine/
    __init__.py        PlanEngine — table execution engine
    types.py           Column types, cell states, plan/execution state dataclasses
    execution.py       Cell operations, gating, locking, cascade revert
    criteria.py        Boolean expression evaluator for acceptance criteria
    audit.py           Execution history tracking
    persistence.py     Plan serialization
  builder_handler.py   Create Workflow workflow (meta-tool, uses runtime utilities)
  app.py               Flask infrastructure (routes, SSE, feedback, state persistence)
  utils.py             Shared display helpers (trunc, field)
  templates/           Observer UI, base layout, CR form, plan editor
  data/
    agent_create_cr.yaml                  CR workflow definition
    agent_create_executable_table.yaml    Table workflow definition
    agent_create_workflow.yaml            Builder workflow definition
    custom_workflows/                     Published custom workflow YAMLs
    workflows/                            Runtime state files (JSON)
```

---

## Discovery and Registration

`app.py` discovers workflows at startup via `_discover_workflows()`:

1. **Built-in YAML workflows** — `agent_create_cr.yaml` and `agent_create_executable_table.yaml` are loaded via `WorkflowRuntime`
2. **Builder** — `builder_handler.py` is registered as a special-case handler
3. **Custom workflows** — all `*.yaml` files in `data/custom_workflows/` are loaded via `WorkflowRuntime`

New workflows published by the builder appear after a server restart.

---

## Backward Compatibility

The `compat.py` module normalizes older YAML formats:

| Old format | New format |
|------------|-----------|
| `proceed.requires: [title, purpose]` | `proceed.gate: {op: AND, conditions: [{type: field_truthy, key: title}, ...]}` |
| `options_ref: submodules` | `options_from: submodules` |
| `computed: sdlc_check` | `compute: {type: set_membership, key: ..., set_ref: sdlc_governed}` |
| Top-level `submodules: [...]` | `option_sets: {submodules: [...]}` |
| Missing `key` in field def | Key inferred from dict key |
| `affects_code` boolean field | `side_effects` injected for cascade clearing |

Existing state files (`data/workflows/*.state.json`) are forward-compatible — the state dict shape is unchanged.

---

## Creating a New Workflow

### Via the Builder (no code)

1. Open the Agent Portal and start the "Create Workflow" workflow
2. Define metadata (ID, title, description)
3. Add lifecycle phases
4. Build nodes with fields, visibility rules, proceed gates, navigation
5. Preview and validate
6. Publish — writes YAML to `data/custom_workflows/`
7. Restart the server to register the new workflow

### Via YAML (manual)

1. Create a `.yaml` file in `data/custom_workflows/`
2. Follow the schema reference above
3. Restart the server

### Features available without Python code

- Fields (text, boolean, select) with instructions and defaults
- Dynamic options (select options depend on another field)
- Side effects (auto-set fields when conditions are met)
- Visibility rules (show/hide fields based on other fields)
- Conditional navigation (show/hide nav based on conditions)
- Branching (proceed to non-sequential target nodes)
- Lists (ordered collections with add/edit/remove/reorder)
- Tables (typed columns, rows, construction + execution)
- Execution engine (cell operations, gating, acceptance criteria)
- Lifecycle tracking with banner
- show_all_fields review nodes

### What still requires Python

- New field types beyond text/boolean/select/computed
- New column types for tables
- New cell operations for the execution engine
- New expression evaluator leaf conditions
- The workflow builder itself (structural editing of nested definitions)
