# Workflow Engine Technical Reference

The runtime that interprets YAML workflow definitions and drives agent interaction through the Agent Portal. This document covers the full engine internals: schema, expression language, action dispatch, control-flow primitives, table execution, rendering, and the schematic visualization engine.

For a user-facing introduction with examples, see the [README](../README.md).

---

## Architecture

```
YAML Definition
      │
 ┌────┴────┐
 │ Runtime │   engine/runtime/__init__.py (WorkflowRuntime)
 └────┬────┘
   ┌──┼──┬──────┐
schema eval render actions
   │    │    │      │
 Parse Gates Page  State
 YAML  Viz  Dict  Changes
       Accept
```

The runtime (`engine/runtime/`) is the single engine that interprets all workflow definitions. It loads YAML, parses it into typed dataclasses, and implements the handler protocol that `app/app.py` consumes.

### Handler Protocol

Every workflow — built-in, custom, or the builder — exposes four methods:

| Method | Purpose |
|--------|---------|
| `default_data()` | Returns initial state dict |
| `render_node(data, workflow_id)` | Returns page dict: `{state, instructions, affordances}` |
| `process_action(data, workflow_id, body)` | Mutates state, returns rendered page or error |
| `resolve_resource(resource, body)` | Translates URL segment to internal action body |

The Flask infrastructure (routes, SSE streaming, feedback diffing, state persistence) is workflow-agnostic. It calls these four methods and never inspects the workflow definition.

### State Model

Each workflow maintains a flat state dict persisted as JSON on disk (`data/workflows/<id>.state.json`). The dict contains:

- `_current_node` — active node ID
- `_visited` — list of visited node IDs (for go_back)
- `_fork_state` — active branch tracking for parallel workflows
- Field keys — one entry per field across all nodes (namespace is global)
- List keys — arrays of items
- Table data — `_table_columns`, `_table_rows`, `_table_properties`
- Execution state — `_execution_plan`, `_execution_state`

### Discovery and Registration

`app/app.py` discovers workflows at startup via `_discover_workflows()`:

1. **Built-in YAML workflows** — `agent_create_cr.yaml` and `agent_create_executable_table.yaml` loaded via `WorkflowRuntime`
2. **Builder** — `engine/builder.py` registered as a special-case handler (not YAML-driven)
3. **Custom workflows** — all `*.yaml` in `data/custom_workflows/` loaded via `WorkflowRuntime`

Workflows declare which renderers are available via a `renderers` list in their registration. The observer UI presents a dropdown for selection.

---

## Content Primitives

Three types of content can appear in any workflow node. They can be mixed freely — a node can have fields alongside a table, or fields alongside a list.

### Fields

Named, typed values. The fundamental unit of data collection.

```yaml
fields:
  title:
    label: Document Title
    type: text
    key: title
    instruction: "A short, descriptive title."
    default: null
```

**Types:**

| Type | Description | Agent Interaction |
|------|-------------|-------------------|
| `text` | Free-form string | Agent provides any string value |
| `boolean` | True/false | Agent selects true or false |
| `select` | Constrained choice | Agent picks from a predefined list |
| `computed` | Read-only, evaluated by the engine | No affordance generated |

**Properties:**

| Property | Purpose |
|----------|---------|
| `key` | State dict key (unique across entire workflow) |
| `label` | Human-readable name |
| `instruction` | Guidance text |
| `default` | Initial value (typically null) |
| `options` | For select: inline list of valid choices |
| `options_from` | For select: reference to a top-level `option_sets` entry |
| `dynamic_options` | For select: options that change based on another field's value |
| `visible_when` | Expression: field hidden (and affordance suppressed) when false |
| `side_effects` | Conditional auto-set of other fields after this field changes |
| `compute` | For computed: expression that produces the field's value |

### Tables

Two-dimensional structures with typed columns and rows. Tables have a **construction phase** (building the structure) and an optional **execution phase** (filling cells at runtime via the integrated execution engine).

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

**Column properties:**
- `name` — column header
- `type` — one of the types above
- `choices` — for choice-list columns: valid option strings
- `rule` — for acceptance-criteria columns: boolean expression tree (see Expression Language)

**Execution** is enabled by setting `execution: true` on a node. The runtime delegates to the PlanEngine (`engine/execution/`) which computes cell states, gating, sequential locking, cascade revert, and acceptance criteria evaluation.

**Cell operations** during execution:

| Operation | Description |
|-----------|-------------|
| `fill` | Set a text or choice-list cell value |
| `amend` | Modify an already-filled cell (triggers cascade revert of downstream cells) |
| `sign` | Apply an electronic signature (actor + timestamp) |
| `re-sign` | Re-sign after an upstream cell was amended |
| `mark_na` | Mark a cross-reference as not applicable |
| `initiate_issue` | Create a child issue reference (VAR or ER) with sequential numbering |

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
    focus: true
```

**Operations:** `add`, `edit`, `remove`, `reorder`. When `focus: true`, a `list_select` affordance lets the agent set a focused item for detailed interaction.

---

## Expression Language

All conditions — gates, visibility, acceptance criteria, navigation guards, router conditions, fork gates, side effect triggers — use the same expression tree schema evaluated by `engine/runtime/evaluator.py`.

### Leaf Conditions

```yaml
{type: field_truthy, key: title}              # data[key] is truthy
{type: field_equals, key: status, value: X}   # data[key] == X
{type: field_not_null, key: title}            # data[key] is not None
{type: table_has_columns}                     # table has >= 1 column
{type: table_has_rows}                        # table has >= 1 row
{type: set_membership, key: X, set_ref: Y}   # data[X] in option_sets[Y]
```

### Acceptance Criteria Leaves

Delegated to `engine/execution/criteria.py` for table execution context:

```yaml
{type: all-executed}                          # all executable columns filled
{type: column, column: 2, operator: is-filled}
{type: column, column: 2, operator: is-signed}
{type: column, column: 3, operator: equals, value: Pass}
{type: column, column: 4, operator: ref-status, value: Closed}
```

### Composite Conditions

```yaml
{op: AND, conditions: [...]}    # all must pass
{op: OR, conditions: [...]}     # at least one must pass
{op: NOT, conditions: [...]}    # first condition inverted
```

Composites nest arbitrarily:

```yaml
{op: AND, conditions: [
  {type: field_truthy, key: name},
  {op: OR, conditions: [
    {type: field_equals, key: severity, value: High},
    {type: field_equals, key: severity, value: Critical}
  ]}
]}
```

### Where Expressions Are Used

| Context | YAML Key | Effect When False |
|---------|----------|-------------------|
| Field visibility | `visible_when` | Field hidden, affordance suppressed |
| Proceed gate | `proceed.gate` | Proceed affordance suppressed |
| Navigation guard | `navigation[].when` | Navigation affordance suppressed |
| Router condition | `router[].when` | Route not taken |
| Fork gate | `fork.gate` | Fork affordance suppressed |
| Side effect trigger | `side_effects[].when` | Side effect does not fire |
| Acceptance criteria | Column `rule` | Row does not pass acceptance |

The evaluator returns `(passed: bool, reason: str)` for debugging — the reason explains why a condition failed.

---

## Navigation and Control Flow

### Sequential Navigation

- **proceed** — advance to the next node in declaration order (or to a specified `target`)
- **go_back** — return to the previous node (fork-aware: returns within branch context)

### Random Access

- **go_to** — jump to any named node

### Terminal Actions

- **submit** — mark current node complete and advance (initializes execution engine if next node has `execution: true`)
- **restart** — reset entire workflow to initial state

### Conditional Navigation

Navigation entries accept a `when` expression. If the condition evaluates false, the affordance is suppressed:

```yaml
navigation:
  - action: go_to
    node: escalation
    label: Escalate
    when: {type: field_equals, key: severity, value: Critical}
```

### Proceed with Target (Branching)

Proceed can jump to a non-sequential node, enabling diamond-shaped convergence:

```yaml
proceed:
  label: Finish
  target: done
  gate: {type: field_truthy, key: resolution}
```

### Routers (Automatic Conditional Branching)

A router node evaluates conditions against the current state and automatically advances to the matching target. No user interaction occurs — the router fires immediately on entry.

```yaml
severity_router:
  title: Route by Severity
  router:
    - when: {type: field_equals, key: severity, value: Low}
      target: fast_track
    - when: {type: field_equals, key: severity, value: Critical}
      target: full_investigation
    - target: standard_review    # default (no when = always matches)
```

Routes are evaluated in order. The first matching route wins. A route without a `when` clause is the default fallback.

Router nodes are mutually exclusive with `proceed` and `fork` — a node is exactly one of: sequential (proceed), routing (router), or parallel (fork).

### Forks (Parallel Branches)

A fork splits execution into parallel branches. Each branch is an independent sequence of nodes. Branches converge at a merge node.

```yaml
parallel_scope:
  title: Parallel Investigation
  fork:
    label: Begin Parallel Tracks
    gate: {type: field_truthy, key: scope_confirmed}
    branches:
      technical:
        label: Technical Track
        nodes: [tech_analysis, tech_findings]
      compliance:
        label: Compliance Track
        nodes: [compliance_review, compliance_findings]
    merge: merge_point

merge_point:
  title: Converge
  instruction: "All tracks complete. Review combined findings."
  show_all_fields: true
  proceed:
    label: Continue
```

**Fork behavior:**
- On entry, the first branch is activated automatically
- Agent works through the active branch's nodes using normal proceed/go_back
- `switch_branch` affordance lets the agent move between branches
- When the last node of a branch is completed, the engine auto-switches to the next incomplete branch
- When all branches are complete, the agent proceeds to the merge node
- `go_back` within a fork stays within the active branch

Forks can nest inside forks, and routers can precede forks — the Parallel Investigation and Comprehensive Change Assessment workflows demonstrate these patterns.

### Node Pause Control

By default, nodes pause and wait for user interaction. Setting `pause: false` causes a node to auto-advance if its proceed gate passes — useful for router nodes or computed-only waypoints that should fire without stopping.

---

## Inter-Field Dependencies

### Dynamic Options

A select field's available options can depend on another field's current value:

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

When `category` changes, `affected_system`'s option list updates automatically. Validation enforces the current option set — if the agent tries to select a value not in the current options, the action is rejected.

### Side Effects

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

Side effects fire immediately after the field is set, before the page is re-rendered. Multiple side effects can fire from the same field change. The feedback system reports auto-set fields as `modified_fields`.

---

## Affordance Generation

Affordances are **derived from content + state**, not declared. The runtime (`engine/runtime/renderer.py`) generates them in this order:

1. **Field affordances** — for each visible, non-computed field: `"Set {label} (current: {value})"`
2. **List affordances** — for each list: add, select, edit, remove, reorder (based on declared operations and current list state)
3. **Navigation affordances** — for each navigation entry whose `when` condition passes
4. **Proceed affordance** — if the proceed gate evaluates to true
5. **Fork affordance** — if a fork exists and its gate passes
6. **Branch switch affordance** — if inside a fork, for switching between branches
7. **Node action affordances** — submit, restart (unconditional if declared)
8. **Table structural affordances** — add_column, set_cell, etc. (based on declared operations)
9. **Execution affordances** — cell operations from `PlanEngine.get_plan_state().next_actions`
10. **Execution complete affordance** — when all acceptance criteria pass

Each affordance is a self-describing object:

```json
{
  "id": "set-severity",
  "label": "Set Severity (current: null)",
  "method": "POST",
  "url": "/agent/my-workflow/set-severity",
  "body": {"action": "set_field", "key": "severity"},
  "parameters": {
    "value": {
      "options": ["Critical", "High", "Medium", "Low"],
      "labels": ["Critical", "High", "Medium", "Low"]
    }
  }
}
```

The `parameters` field appears only for constrained choices (select fields, choice-list cells). Free-text fields omit it.

---

## Structured Feedback

After each action, the engine computes a diff between before and after states:

| Field | Description |
|-------|-------------|
| `outcome` | The field or action that was directly acted upon |
| `new_fields` | Fields that appeared (became visible) as a result |
| `modified_fields` | Fields whose values changed as a side effect |
| `removed_fields` | Fields that disappeared (became hidden) |
| `new_affordances` | Affordances that became available |
| `removed_affordances` | Affordances that were suppressed |
| `modified_affordances` | Affordances whose labels changed (e.g., field value updated) |

Feedback is delivered as an SSE `navigate` event to all connected observers.

---

## Table Execution Engine

The PlanEngine (`engine/execution/`) manages the runtime state of a table after construction is complete.

### Cell States

| State | Meaning |
|-------|---------|
| `empty` | No value, ready to fill |
| `filled` | Has a value |
| `signed` | Has an electronic signature |
| `na` | Marked not applicable |
| `locked` | Blocked by sequential execution (upstream cell not yet filled) |
| `gated` | Blocked by unmet row prerequisites |
| `static` | Non-executable column (ne- prefix), display only |
| `pass` | Acceptance criteria met |
| `pending` | Acceptance criteria not yet met |

### Gating and Locking

**Row gating:** A row with `ne-prerequisite` column entries is blocked until all referenced prerequisite rows have passed their acceptance criteria.

**Sequential locking:** When `sequential_execution` is true, executable cells in a row are locked left-to-right. Cell N is locked until cell N-1 is filled.

### Cascade Revert

When a cell is amended after downstream cells have been filled, those downstream cells are cleared. This maintains evidence integrity — if an upstream value changes, downstream evidence collected against the old value is invalidated. The `cascade_revert_exempt` flag on specific cells can opt out of this behavior.

### Acceptance Criteria

Each row can have an `ae-acceptance-criteria` column with a `rule` expression. The engine evaluates this automatically after every cell mutation. When all rows pass, the execution is complete and a completion affordance is generated.

### Issue Numbering

`initiate_issue` operations generate sequential issue numbers scoped to the workflow (e.g., VAR-001, VAR-002). The counter persists in the execution state.

---

## YAML Schema Reference

Complete workflow definition with all supported keys:

```yaml
# ── Identity ──────────────────────────────────────
workflow_title: My Workflow
workflow_description: One-line summary.

# ── Shared Data (optional) ────────────────────────
option_sets:
  categories: [A, B, C]
  subcategories: [X, Y, Z]

# ── Column Type Catalog (optional) ────────────────
column_types:
  ne-free-text:
    label: Free Text
    category: non-executable
    description: "Static text content."
  ex-choice-list:
    label: Choice List
    category: executable
    description: "Constrained selection during execution."
  ae-acceptance-criteria:
    label: Acceptance
    category: auto-executed
    description: "Pass/fail evaluation."

# ── Nodes ─────────────────────────────────────────
nodes:

  # ── Standard Node (sequential) ──────────────────
  step_one:
    title: Step One
    instruction: "What to do at this step."
    show_all_fields: false          # true = aggregate all fields from every node
    pause: true                     # false = auto-advance if gate passes

    # Content: fields
    fields:
      my_field:
        label: My Field
        type: text                  # text | boolean | select | computed
        key: my_field
        instruction: "Guidance text."
        default: null
        visible_when:               # expression (hide field when false)
          type: field_truthy
          key: other_field
        side_effects:
          - when: {type: field_equals, key: my_field, value: X}
            set: {derived_field: Y}
        # For select:
        # options: [A, B, C]
        # options_from: categories       (references option_sets)
        # dynamic_options:
        #   source_key: parent_field
        #   mapping: {val1: [opt1, opt2], val2: [opt3, opt4]}
        #   default: []
        # For computed:
        # compute: {type: set_membership, key: my_field, set_ref: categories}

    # Content: lists
    lists:
      my_list:
        label: Item
        item_schema:
          name: {type: text, required: true}
          status: {type: select, options: [Active, Inactive]}
        operations: [add, edit, remove, reorder]
        focus: true                 # enable focused-item pattern

    # Content: table
    table:
      column_type_catalog: column_types
      properties:
        sequential_execution: {type: boolean, default: false}
      operations: [add_column, remove_column, rename_column, set_column_type,
                   add_row, remove_row, set_cell, set_choices, set_rule,
                   set_prerequisites, set_property]

    # Execution engine (requires table)
    execution: false

    # Navigation
    navigation:
      - action: go_back
        label: Go back
      - action: go_to
        node: other_step
        label: Jump to Other
        when: {type: field_equals, key: mode, value: advanced}

    # Proceed (sequential advance)
    proceed:
      label: Continue
      gate: {op: AND, conditions: [{type: field_truthy, key: my_field}]}
      target: step_three            # optional: jump to non-sequential node

    # Terminal actions
    actions:
      - action: submit
        label: Submit
      - action: restart
        label: Start Over

  # ── Router Node (automatic conditional branching) ─
  my_router:
    title: Route by Priority
    router:
      - when: {type: field_equals, key: priority, value: High}
        target: urgent_path
      - when: {type: field_equals, key: priority, value: Low}
        target: simple_path
      - target: default_path        # no when = default fallback

  # ── Fork Node (parallel branches) ──────────────
  my_fork:
    title: Parallel Execution
    fork:
      label: Begin Parallel Tracks
      gate: {type: field_truthy, key: scope_confirmed}    # optional
      branches:
        track_a:
          label: Track A
          nodes: [node_a1, node_a2]
        track_b:
          label: Track B
          nodes: [node_b1, node_b2]
      merge: convergence_node
```

---

## Action Dispatch

All state mutations flow through `engine/runtime/actions.py`. The dispatcher (`dispatch()`) receives the workflow definition, current state dict, workflow ID, and action body.

### Field Actions

| Action | Body | Effect |
|--------|------|--------|
| `set_field` | `{action, key, value}` | Sets field value, fires side effects, recomputes computed fields |

Validation: select fields reject values not in current options. Dynamic options are resolved before validation.

### List Actions

| Action | Body | Effect |
|--------|------|--------|
| `list_add` | `{action, list_key, item: {field: val, ...}}` | Appends item (validated against schema) |
| `list_edit` | `{action, list_key, index, updates: {field: val}}` | Modifies item at index |
| `list_remove` | `{action, list_key, index}` | Removes item at index |
| `list_reorder` | `{action, list_key, from_index, to_index}` | Moves item |
| `list_select` | `{action, list_key, index}` | Sets focused item (when focus=true) |

### Navigation Actions

| Action | Body | Effect |
|--------|------|--------|
| `proceed` | `{action: proceed}` | Advance (gate-checked, target-aware, fork-aware) |
| `go_back` | `{action: go_back}` | Return to previous node |
| `go_to` | `{action: go_to, node: id}` | Jump to named node |
| `submit` | `{action: submit}` | Terminal advance |
| `restart` | `{action: restart}` | Reset to initial state |
| `switch_branch` | `{action: switch_branch, branch: id}` | Change active fork branch |

### Table Structural Actions

| Action | Body | Effect |
|--------|------|--------|
| `add_column` | `{action, name, type}` | Add typed column |
| `remove_column` | `{action, index}` | Remove column at index |
| `rename_column` | `{action, index, name}` | Rename column |
| `set_column_type` | `{action, index, type}` | Change column type |
| `add_row` | `{action}` | Append empty row |
| `remove_row` | `{action, index}` | Remove row |
| `set_cell` | `{action, row, column, value}` | Set cell value |
| `set_choices` | `{action, column, choices: [...]}` | Set choice-list options |
| `set_rule` | `{action, column, rule: {expression}}` | Set acceptance criteria |
| `set_prerequisites` | `{action, row, prerequisites: [...]}` | Set row dependencies |
| `set_property` | `{action, key, value}` | Set table property |

### Table Execution Actions

| Action | Body | Effect |
|--------|------|--------|
| `cell_action` | `{action, operation, row, column, ...}` | Cell mutation (fill, sign, mark_na, initiate_issue, amend, re-sign) |
| `complete` | `{action: complete}` | Exit execution, proceed to next node |

### Internal Algorithms

**`_enter_node()`** — called whenever the current node changes. Handles:
- Router auto-routing: evaluates conditions and advances immediately
- Auto-advance: if `pause: false` and proceed gate passes, advances without stopping

**`_activate_fork()`** — initializes parallel branch state, sets first branch as active.

**`_branch_proceed()`** — advances within a branch. When branch ends, auto-switches to next incomplete branch. When all branches complete, proceeds to merge node.

---

## Backward Compatibility

The `compat.py` module normalizes older YAML formats to the canonical schema:

| Old Format | Canonical Format |
|------------|-----------------|
| `proceed.requires: [title, purpose]` | `proceed.gate: {op: AND, conditions: [{type: field_truthy, key: title}, ...]}` |
| `options_ref: submodules` | `options_from: submodules` |
| `computed: sdlc_check` | `compute: {type: set_membership, key: ..., set_ref: sdlc_governed}` |
| Top-level `submodules: [...]` | `option_sets: {submodules: [...]}` |
| Missing `key` in field def | Key inferred from dict key |
| `affects_code` boolean field | `side_effects` injected for cascade clearing |

State files (`data/workflows/*.state.json`) are forward-compatible — the state dict shape is unchanged.

---

## Renderer System

### Architecture

The observer UI (`app/templates/agent_observer.html`) is a thin shell that:
1. Loads Jinja variables (`_WFE_ALLOWED_RENDERERS`, `_WFE_STREAM_URL`) into `window`
2. Connects to the SSE stream
3. Delegates all rendering to the active renderer from `app/static/renderers/`

### Renderer Protocol

Each renderer registers with the registry (`registry.js`) and implements:

```javascript
{
  id: "unique-id",
  label: "Display Name",
  format: "simple",          // hierarchical grouping
  verbosity: "default",      // "default" or "verbose"
  style: "light",            // "light", "dark", etc.
  init(container),           // build DOM skeleton (called once)
  update(state, msg, feedback),  // redraw on state change
  activate(),                // called when switching to this renderer
  deactivate()               // called when switching away
}
```

### Built-in Renderers

| File | Renderers | Description |
|------|-----------|-------------|
| `simple-shared.js` | — | Shared rendering functions: `wfRenderBanner`, `wfRenderFields`, `wfRenderTable`, `wfRenderAffordances`, `wfRenderFeedback`, `wfRenderStateProps` |
| `simple.js` | Simple Light, Simple Dark, Simple Light Verbose, Simple Dark Verbose | Card-based layout with CSS variables for theming |
| `exp-a.js` | Experimental A | Blueprint-style layout |
| `exp-b.js` | Experimental B | Card grid layout |
| `exp-c.js` | Experimental C | Tree outline layout |
| `raw.js` | Raw | JSON pretty-printer |

All renderers handle all content types generically (fields, tables, lists, execution tables, lifecycle banner). Unknown state keys are rendered via `wfRenderStateProps` for forward compatibility.

---

## Schematic Visualization Engine

The schematic engine (`app/static/schematic.js`) renders interactive workflow topology diagrams. It is content-agnostic — callers provide a `nodeRenderer(item, status)` callback returning arbitrary HTML.

### Pipeline

```
Definition → Spine → Flatten → Layout → Render
```

1. **`definitionToSpine(definition)`** — Parses workflow definition (nodes, routers, forks) into a recursive spine model with three segment types:
   - **Step** — a single node
   - **Gate** (OR) — a decision point with conditional branches
   - **Split** (AND) — parallel branches that converge

2. **`flattenSpine(spine)`** — Converts recursive spine to a flat sequence of layout items with depth and branch tracking.

3. **`treeOrderLines(lines, opts)`** — Orders items for visual flow (top-to-bottom with branches side-by-side).

4. **`layout(lines, opts)`** — Computes canvas coordinates (x, y, width, height) for every item. Handles branch spacing, convergence points, and nested structures.

5. **`renderHybrid(spine, container, execState, opts)`** — The primary render function. Nodes are real HTML `<div>` elements positioned absolutely over a `<canvas>` that draws topology wires, bars, and routing labels.

### Measurement-First Approach

Layout depends on actual content dimensions:

1. Nodes are rendered in a hidden container with the caller's `nodeRenderer` callback
2. DOM heights and widths are measured via `setSpineHeights()`
3. Measurements are injected into the spine
4. Layout adapts to actual content size — no height heuristics

### Node Handles

Wires attach to nodes at configurable points:
- `handleY` — fraction (0.0 = top, 1.0 = bottom)
- `handlePx` — fixed pixel offset from top

The detailed flowchart renderer uses `handlePx` to attach wires at card header height.

### Interactive Collapse/Expand

Branch points (gates, splits) are clickable by default. Clicking collapses/expands the branch's descendant nodes. The engine handles spine pruning and re-render internally.

**`focusNode` mode:** When a `focusNode` ID is provided, auto-collapse shows only the path to the current node. Used by the lifecycle banner in the workflow observer.

### Visual Language

| Element | Appearance |
|---------|------------|
| Step nodes | Rounded pills or rich HTML cards (caller-provided) |
| Gate (OR) nodes | Inline SVG hexagons |
| Split (AND) nodes | CSS border-radius rectangles with bars |
| Flow wires | Solid lines (sequential), with routing condition labels |
| Collapse wires | Dashed horizontal connectors between collapsed branch-point and continuation |

### Usage

```javascript
// Standalone schematic
const spine = definitionToSpine(workflowDefinition);
renderHybrid(spine, containerDiv, executionState, {
  nodeRenderer: (item, status) => `<div class="node">${item.title}</div>`,
  focusNode: currentNodeId,       // optional: auto-collapse to this node
  interactive: true               // optional: enable collapse/expand (default true)
});
```

The Workshop page (`/workshop`) provides an interactive test harness with 8+ example workflow definitions for experimenting with the schematic engine.

---

## SSE Event Protocol

The observer connects to `/agent/<id>/stream` and receives:

| Event | Payload | When |
|-------|---------|------|
| `init` | Full page dict | On connection |
| `action` | `{action, label, ...}` | When an action is submitted |
| `result` | Full page dict | After action is processed |
| `navigate` | `{feedback, node, ...}` | After state change with feedback diff |

Events are JSON-encoded. The renderer's `update()` method receives the parsed page dict, the raw SSE message, and the feedback object.

---

## Extension Points

### What YAML Can Do (no Python)

- Fields (text, boolean, select, computed) with all properties
- Dynamic options, side effects, visibility rules
- Conditional navigation, proceed gates with targets
- Routers (automatic conditional branching)
- Forks (parallel branches with merge convergence)
- Lists (ordered collections with full CRUD)
- Tables (typed columns, construction + execution)
- Execution engine (cell operations, gating, acceptance criteria)
- `show_all_fields` review/summary nodes
- Option sets, column type catalogs

### What Requires Python

- New field types beyond text/boolean/select/computed
- New table column types
- New cell operations for the execution engine
- New expression evaluator leaf conditions
- The workflow builder itself (structural editing of nested definitions)
- Custom renderers

### Known Gaps

- **Hot reload** — Published workflows require a server restart. A reload endpoint would let the builder register new workflows immediately.
- **Custom field types** — date, number, rich text, file upload would expand what workflows can collect.
- **Custom column types** — User-defined column types would need a type registry with cell operations and rendering hints.
- **Renderer plugins** — The renderer registry is fixed. A plugin system would enable domain-specific views.
