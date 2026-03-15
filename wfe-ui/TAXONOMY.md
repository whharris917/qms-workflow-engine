# Workflow Engine Taxonomy

A complete inventory of the parts that compose workflows, organized by abstraction level. Everything in this system is built from these primitives.

---

## Level 0: Workflow

A workflow is an ordered graph of **nodes** with a **lifecycle banner** tracking progress. It has a title, a description, and produces a state dict that evolves as the agent interacts with it.

Every workflow, whether built-in or custom, conforms to this contract:
- Returns a **page dict**: `{state, instructions, affordances}`
- Accepts **actions** that mutate its state
- Persists state as a JSON file on disk

---

## Level 1: Structural Primitives

These are the bones of every workflow.

### Node
A discrete step in a workflow. Has an ID, title, instruction text, and maps to a lifecycle phase. The agent sees one node at a time.

### Lifecycle Banner
An ordered sequence of phase labels displayed as a progress indicator. Each node maps to one phase. Multiple nodes can share a phase.

### Navigation
How the agent moves between nodes:
- **proceed** — advance to the next node (sequential)
- **go_back** — return to the previous node (sequential)
- **go_to** — jump to a named node (random access)
- **submit** — terminal transition (marks completion)
- **restart** — reset to initial state

### Proceed Gate
A condition that must be satisfied before `proceed` becomes available. Currently supports: "all listed field keys must be non-null." The gate controls when the proceed affordance appears.

---

## Level 2: Content Primitives

These are the things that live inside nodes — the material the agent interacts with.

### Field
A named, typed, key-value pair. The fundamental unit of data collection.

| Type | Description | Interaction |
|------|-------------|-------------|
| **text** | Free-form string | Agent provides any string |
| **boolean** | True/false | Agent selects true or false |
| **select** | Constrained choice | Agent picks from a predefined list |

**Field properties:**
- **label** — Human-readable name
- **key** — Machine-readable state key (unique across workflow)
- **instruction** — Guidance text shown alongside the field
- **default** — Initial value (typically null)
- **options** — For select: list of valid choices
- **visible_when** — Conditional visibility rule: `{key: value}` or `{key: "not_null"}`

### Table
A two-dimensional structure of **columns** and **rows**. Richer than fields — supports typed columns, cell-level operations, and an integrated execution engine.

**Table properties:**
- **sequential_execution** — If true, executable columns must be filled left-to-right

#### Column Types

Columns are classified by when they get filled:

| Category | Prefix | Filled During | Examples |
|----------|--------|---------------|----------|
| **Non-executable** | `ne-` | Construction (authoring) | `ne-free-text`, `ne-prerequisite` |
| **Executable** | `ex-` | Execution (runtime) | `ex-free-text`, `ex-choice-list`, `ex-cross-reference`, `ex-signature` |
| **Auto-executed** | `ae-` | Automatically by system | `ae-acceptance-criteria` |

#### Column Properties
- **name** — Column header
- **type** — One of the column types above
- **choices** — For choice-list columns: valid option strings
- **rule** — For acceptance-criteria columns: boolean expression tree

#### Cell Operations (during execution)
- **fill** — Set a text or choice-list cell value
- **sign** — Apply an electronic signature (actor + timestamp)
- **mark_na** — Mark a cross-reference as not applicable
- **initiate_issue** — Create a child issue reference (VAR or ER)

### Acceptance Criteria
A boolean expression that evaluates automatically during execution, gating row completion.

**Expression structure:** `{op: "AND"|"OR", conditions: [...]}`

**Leaf conditions:**
- `all-executed` — Every executable column in the row is filled
- `column is-filled` — A specific column has a value
- `column is-signed` — A specific column has a signature
- `column equals "value"` — A specific column matches a string
- `column ref-status "value"` — A cross-reference's status matches

### Prerequisites
Row-level dependency declarations. A row with prerequisites is **gated** (blocked from execution) until all prerequisite rows have passed their acceptance criteria.

---

## Level 3: Behavioral Primitives

These govern how content primitives interact at runtime.

### Execution Engine
Manages the runtime state of a table after construction. Computes:
- **Cell status** — empty, filled, signed, na, locked, gated, static, pass, pending
- **Row gating** — Which rows are blocked by unmet prerequisites
- **Sequential locking** — Which cells are blocked by unfilled upstream cells
- **Cascade revert** — When a cell is modified, downstream cells are cleared
- **Acceptance evaluation** — Whether a row's criteria have passed
- **Next actions** — Which cells the agent can act on right now

### Visibility Rules
Fields can be conditionally shown/hidden based on the values of other fields. When a field is invisible, its affordance is also suppressed.

### Affordance Generation
Affordances are computed dynamically from the current state. They are not stored — they are derived. The pattern:
1. Examine current node definition
2. For each visible field, generate a "Set {label}" affordance
3. For each navigation entry, generate a navigation affordance
4. If proceed gate is satisfied, generate a proceed affordance
5. For each node action, generate an action affordance
6. For tables: generate structural affordances (add column, set cell, etc.)
7. For execution: generate cell-action affordances from engine's next_actions

### Feedback
After each action, the system computes a diff between before/after states:
- **outcome** — The field that was directly acted upon
- **new_fields** — Fields that appeared as a result
- **modified_fields** — Fields that changed as a side effect
- **new_affordances** — Affordances that became available
- **modified_affordances** — Affordances whose labels changed

---

## Level 4: Composition Patterns

How the primitives combine in practice.

### Field-Based Workflow
Nodes contain fields. Agent fills fields, proceeds through gates, navigates between nodes.
- **Built-in example:** Create CR (cr_handler)
- **Custom examples:** Any workflow created by the builder (generic_handler)
- **Rendering:** `state.fields` → field cards

### Table-Based Workflow
Nodes manage a table. Agent constructs the table structure, reviews it, then executes it.
- **Built-in example:** Create Executable Table (table_handler)
- **Rendering:** `state.table` → construction table, `state.execution_table` → execution table

### Structural Workflow
Nodes manage a complex nested data structure (not fields, not a table). Agent builds something through structural affordances.
- **Built-in example:** Create Workflow (workflow_builder_handler)
- **Rendering:** Extra state keys → generic object rendering via `wfRenderStateProps`

### Hybrid (future)
A workflow that combines fields and tables in the same node. Not yet implemented, but the rendering layer already supports it — `state.fields` and `state.table` can coexist.

---

## What Can Be Extended

### By agents today (via Create Workflow)
- New field-based workflows with any combination of:
  - text, boolean, select fields
  - Visibility rules
  - Proceed gates
  - Navigation (go_back, go_to)
  - Terminal actions (submit, restart)
  - show_all_fields aggregation
  - Any number of nodes with any lifecycle structure

### Not yet extensible (requires Python)
- New field types beyond text/boolean/select/computed
- New column types for tables
- New cell operations for the execution engine
- New expression evaluator leaf conditions
- Custom renderers as plugins

---

## The Standard Library (what ships built-in)

### Engine
| Component | Purpose |
|-----------|---------|
| `runtime/` (WorkflowRuntime) | Unified engine interpreting any YAML workflow definition |
| `builder_handler.py` | Workflow builder (meta-tool, uses runtime utilities) |
| `engine/` (PlanEngine) | Table execution engine (gating, locking, acceptance) |

### Field Types
| Type | Description |
|------|-------------|
| text | Free-form string |
| boolean | True/false toggle |
| select | Constrained choice (static, dynamic, or from option_sets) |
| computed | Read-only, evaluated by the engine |

### Column Types
| Type | Category | Purpose |
|------|----------|---------|
| ne-free-text | Non-executable | Static text content |
| ne-prerequisite | Non-executable | Row dependency declarations |
| ex-free-text | Executable | Free-form evidence/output |
| ex-choice-list | Executable | Constrained selection |
| ex-cross-reference | Executable | External artifact links |
| ex-signature | Executable | Identity + timestamp |
| ae-acceptance-criteria | Auto-executed | Pass/fail evaluation |

### Renderers
All 7 renderers handle all building blocks generically:
- Lifecycle banner, instructions, fields, table, execution_table, affordances, feedback
- Unknown state keys rendered via `wfRenderStateProps` (forward-compatible)

---

## Gaps and Future Directions

1. ~~**Table as composable component**~~ — **DONE.** Tables can now appear in any node via the `table` key.

2. **Custom field types** — The runtime supports text/boolean/select/computed. Richer types (date, number, rich text, file upload) would expand what custom workflows can collect.

3. **Custom column types** — The executable table has a fixed set of column types. User-defined column types would need a type registry with associated cell operations and rendering hints.

4. ~~**Conditional navigation**~~ — **DONE.** Navigation entries accept `when` expressions. Proceed gates accept `target` for non-sequential jumps. Full branching workflows are supported.

5. ~~**Inter-field dependencies**~~ — **DONE.** `dynamic_options` on select fields (options depend on another field). `side_effects` for auto-population when conditions are met.

6. **Custom renderers** — The renderer registry is fixed at 7. A plugin system for renderers would let users build domain-specific views.

7. **Hot reload** — Published workflows require a server restart. A reload endpoint would let the builder register new workflows immediately.
