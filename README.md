# QMS Workflow Engine

A declarative workflow runtime that interprets YAML workflow definitions and exposes them simultaneously to AI agents (via a resource-oriented API) and to humans (via a real-time observer UI).

Workflows are pure data. You define nodes, fields, conditions, and routing in YAML — the engine handles state management, affordance generation, expression evaluation, and visualization. No Python code is required for new workflows.

## Quick Start

```bash
cd qms-workflow-engine
pip install flask pyyaml
python run.py
```

Open `http://127.0.0.1:5000/agent` to see the Agent Portal — a listing of all available workflows with their current state.

## What You Can Build

The engine supports workflows ranging from simple linear forms to complex branching processes with parallel execution tracks:

- **Field-based workflows** — Collect structured data through text, boolean, select, and computed fields with validation gates and conditional visibility
- **Table-based workflows** — Build evidence tables with typed columns, then execute them with gating, sequential locking, and acceptance criteria
- **Branching workflows** — Route agents through different paths based on field values using routers (automatic conditional branching)
- **Parallel workflows** — Fork into concurrent execution tracks that converge at merge points
- **Hybrid workflows** — Combine fields, lists, and tables within the same node

Four example workflows ship in `data/custom_workflows/`:

| Workflow | Demonstrates |
|----------|-------------|
| Create Deviation | Fields, visibility rules, proceed gates |
| Incident Response | Dynamic options, side effects, lists, execution tables |
| Parallel Investigation | Routers, forks, merges, multi-track parallel execution |
| Comprehensive Change Assessment | All primitives: router, fork, lists, tables, computed fields, rework loops |

Three built-in workflows ship in `data/`:

| Workflow | Purpose |
|----------|---------|
| Create CR | Author a Change Record through a guided multi-step form |
| Create Executable Table | Build a typed evidence table, then execute it |
| Create Workflow | Meta-tool: build new workflows through the engine itself (44 actions) |

## How It Works

### The Interaction Loop

1. Agent (or human via observer UI) sees a **page**: current node's instructions, visible fields, and available affordances
2. Agent picks an affordance and POSTs it back
3. Engine validates the action, mutates state, evaluates side effects and visibility rules
4. Engine re-renders the page with updated state and new affordances
5. **Structured feedback** reports what changed: which field was set, what appeared or disappeared, what new affordances became available

### Affordance-Driven Design

Agents don't need to know the workflow structure. Every valid action is presented as a self-describing affordance with a URL, HTTP method, body template, and parameter options for constrained choices. The agent just picks one and sends it.

Affordances are **derived from state**, not declared. When a field becomes visible, its affordance appears. When a gate opens, the proceed affordance appears. When a fork activates, branch-switching affordances appear. When all acceptance criteria pass, the completion affordance appears.

### Observer UI

The observer (`/agent/<id>/observe`) connects via Server-Sent Events and renders the workflow in real time. Multiple renderer styles are available:

| Renderer | Description |
|----------|-------------|
| Simple (light/dark, default/verbose) | Card-based layout — the default |
| Experimental A | Blueprint-style layout |
| Experimental B | Card grid |
| Experimental C | Tree outline |
| Raw | JSON pretty-printer for debugging |

All renderers consume the same page dictionary. The **schematic engine** draws interactive workflow topology diagrams — a lifecycle banner showing progress and full definition flowcharts — using an HTML-over-canvas hybrid approach where nodes are real DOM elements positioned by the layout engine over a canvas that draws only topology wires.

## Creating a Workflow

### Option 1: The Builder (no code)

1. Open the Agent Portal and start **Create Workflow**
2. Define metadata (ID, title, description) and lifecycle phases
3. Build nodes with fields, visibility rules, proceed gates, conditional navigation, lists, tables
4. Add control-flow: routers for conditional branching, forks for parallel tracks
5. Preview, validate, and publish — writes YAML to `data/custom_workflows/`
6. Restart the server to register the new workflow

### Option 2: Write YAML Directly

Create a `.yaml` file in `data/custom_workflows/` and restart the server.

**Minimal example** — a two-step form:

```yaml
workflow_title: My Workflow
workflow_description: A simple two-step workflow.

nodes:
  gather:
    title: Gather Information
    instruction: "Provide the required details."
    fields:
      name:
        label: Name
        type: text
        key: name
        instruction: "Enter a name."
      priority:
        label: Priority
        type: select
        key: priority
        options: [Low, Medium, High]
    proceed:
      label: Continue
      gate:
        op: AND
        conditions:
          - {type: field_truthy, key: name}
          - {type: field_truthy, key: priority}

  review:
    title: Review
    instruction: "Confirm the details are correct."
    show_all_fields: true
    actions:
      - action: submit
        label: Submit
      - action: restart
        label: Start Over
```

**Branching example** — route based on a field value:

```yaml
workflow_title: Triage Workflow
workflow_description: Routes to different paths based on severity.

nodes:
  intake:
    title: Intake
    instruction: "Classify the issue."
    fields:
      severity:
        label: Severity
        type: select
        key: severity
        options: [Low, Medium, High, Critical]
    proceed:
      label: Continue
      gate: {type: field_truthy, key: severity}

  severity_router:
    title: Route by Severity
    router:
      - when: {type: field_equals, key: severity, value: Low}
        target: fast_track
      - when: {type: field_equals, key: severity, value: Critical}
        target: full_investigation
      - target: standard_review    # default

  fast_track:
    title: Fast Track
    instruction: "Low severity — quick resolution."
    fields:
      resolution:
        label: Resolution
        type: text
        key: resolution
    proceed:
      label: Done
      target: close
      gate: {type: field_truthy, key: resolution}

  standard_review:
    title: Standard Review
    instruction: "Assess and resolve."
    # ... fields ...
    proceed:
      label: Done
      target: close

  full_investigation:
    title: Full Investigation
    instruction: "Critical — thorough investigation required."
    # ... fields ...
    proceed:
      label: Done
      target: close

  close:
    title: Complete
    show_all_fields: true
    actions:
      - action: submit
        label: Close
```

For the complete YAML schema, expression language reference, control-flow primitives, and all engine internals, see [docs/ENGINE.md](docs/ENGINE.md).

## API Endpoints

### Workflow Runtime

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/agent` | Portal — lists all workflows with current state |
| GET | `/agent/<id>` | Current page (state, instructions, affordances) |
| POST | `/agent/<id>` | Process an action |
| POST | `/agent/<id>/<resource>` | Resource-oriented action (affordance URL) |
| GET | `/agent/<id>/observe` | Observer UI (SSE + renderers) |
| GET | `/agent/<id>/stream` | SSE event stream (init, action, result, navigate) |

### Plan Execution (Table Engine)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/cr/<id>/plan` | Authoring data (columns, rows, properties) |
| GET | `/api/cr/<id>/execution` | Execution state with affordances |
| POST | `/api/cr/<id>/execution/start` | Initialize execution |
| POST | `/api/cr/<id>/execution/cell` | Cell mutation (fill, sign, mark_na, initiate_issue) |
| GET | `/api/cr/<id>/execution/row/<n>` | Single row state |
| GET | `/api/cr/<id>/execution/history/<n>` | Row audit trail |

### Other Pages

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Landing page |
| GET | `/qms` | QMS dashboard |
| GET | `/manual/<slug>` | Quality Manual browser |
| GET | `/templates` | Document type template editor |
| GET | `/create/cr` | CR authoring form |
| GET | `/workshop` | Schematic engine test harness |

## Project Structure

```
qms-workflow-engine/
├── run.py                          # Entry point
├── engine/
│   ├── runtime/                    # Unified workflow runtime
│   │   ├── __init__.py             #   WorkflowRuntime class
│   │   ├── schema.py               #   Dataclasses (WorkflowDef, NodeDef, FieldDef, ...)
│   │   ├── evaluator.py            #   Expression evaluator (gates, visibility, conditions)
│   │   ├── actions.py              #   Action dispatcher (all state mutations)
│   │   ├── renderer.py             #   Page rendering + affordance generation
│   │   └── compat.py               #   Legacy YAML normalization
│   ├── execution/                  # Table execution engine
│   │   ├── execution.py            #   PlanEngine (cell states, gating, locking, cascade)
│   │   ├── types.py                #   Column types, cell states, plan/execution state
│   │   ├── criteria.py             #   Acceptance criteria evaluator
│   │   ├── audit.py                #   Execution history tracking
│   │   └── persistence.py          #   Plan serialization
│   ├── builder.py                  # Create Workflow meta-tool (44 actions)
│   └── utils.py                    # Shared display helpers
├── app/
│   ├── app.py                      # Flask app (routes, SSE, feedback, state persistence)
│   ├── api.py                      # Plan execution REST API
│   ├── templates/                  # Jinja2 templates (observer, workshop, ...)
│   └── static/
│       ├── schematic.js            # Schematic layout engine (topology visualization)
│       └── renderers/              # Pluggable renderer system (7 renderers)
├── data/
│   ├── agent_create_cr.yaml        # Built-in: CR authoring workflow
│   ├── agent_create_executable_table.yaml  # Built-in: table builder
│   ├── agent_create_workflow.yaml  # Built-in: workflow builder definition
│   ├── custom_workflows/           # User-published workflows (auto-discovered at startup)
│   └── workflows/                  # Runtime state files (JSON, persisted per workflow)
└── docs/
    └── ENGINE.md                   # Technical reference (full schema, expression language, internals)
```

## Relationship to Pipe Dream

This repository is a submodule of [pipe-dream](https://github.com/whharris917/pipe-dream), the parent project that houses the QMS (Quality Management System) and the Flow State application. Development of this engine is governed by the QMS change control process.
