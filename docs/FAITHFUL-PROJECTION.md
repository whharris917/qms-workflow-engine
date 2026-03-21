# Faithful Projection

*Architecture for Human-Agent Parity by Construction*

---

## 1. The Core Idea

A **faithful projection** is a renderer that projects an engine's output completely, without invention, in whatever representational form it chooses. The term consolidates three independent constraints into a single architectural concept:

- **Lossless.** Nothing the engine produces is omitted.
- **Non-additive.** Nothing the projection displays is invented.
- **Representationally free.** The projection chooses its own form.

A projection that satisfies all three is *faithful*. A projection that violates any one is not.

The practical consequence: if the engine is the single source of semantic truth, and every interface — human UI, machine API, raw inspector — is a faithful projection of the same engine output, then every participant sees the same information and has access to the same actions. Parity is not a feature to be implemented; it is a structural property that holds as long as the projections remain faithful.

---

## 2. Why "Faithful Projection"

The longer formulation — "lossless, non-additive, and representationally free" — describes the constraints precisely but names nothing. It is a specification, not a concept. Engineers don't say "I'm building a lossless, non-additive, representationally free renderer." They say "I'm building a faithful projection."

The word *faithful* carries the right connotation: the projection is loyal to its source. It does not editorialize. It does not omit. It does not fabricate. It renders what the engine says, fully and honestly, in its own visual language.

The word *projection* carries the right structural implication: a projection is a lower-dimensional view of a higher-dimensional object. A shadow is a projection of a solid. A map is a projection of terrain. A rendered page is a projection of engine state. The source is singular and authoritative; the projections are plural and subordinate. Multiple projections of the same source coexist without contradiction because they share the same semantic content and differ only in representational form.

---

## 3. The Canonical Payload

Every page in the system is a faithful projection of a **canonical payload** — a structured dict returned by `GET` on the page's URL:

```json
{
  "state": {
    "page": "agent",
    "page_title": "Agent Portal",
    "workflows": [...]
  },
  "instructions": "Available workflows. Create new instances or open existing ones.",
  "affordances": [
    {"id": 1, "label": "Open Create CR (a3f7c2d1: initiation)", "method": "GET", "url": "/agent/create-cr/a3f7c2d1"},
    {"id": 2, "label": "Delete Create CR (a3f7c2d1)", "method": "POST", "url": "/agent/create-cr/a3f7c2d1/delete", "body": {}},
    {"id": 3, "label": "New Create CR instance", "method": "POST", "url": "/agent/create-cr/new", "body": {}}
  ]
}
```

The three top-level keys partition the semantic space:

- **`state`** — What is true. The current values of all fields, the topology of the workflow, the position within it, any tables or lists, any metadata. This is the document.
- **`instructions`** — What the participant should know. Contextual guidance for the current state. This is the engine speaking to whoever is looking.
- **`affordances`** — What is possible. Every action that can be taken from this state, with the method, URL, parameters, and body needed to execute it. This is the complete action space.

The same URL serves the same payload to every participant. Content negotiation determines the form: `Accept: application/json` returns the raw payload; a browser request returns an HTML page whose renderer projects it.

### 3.1 The Payload Is Not Stored

The canonical payload is computed at request time. `state.workflows` is assembled by scanning instance files on disk. `affordances` is derived from the current state by the AffordanceSource protocol. `instructions` comes from the workflow definition. Nothing is persisted as a payload; the payload is a projection of the engine's live state. The only persisted artifacts are instance state files — everything else is synthesized.

This means the payload is always current. There is no cache to invalidate, no stored representation to drift from the truth. Every GET recomputes from the source.

### 3.2 `state.page` and the URL

The `state.page` field identifies the semantic page. Its value matches the URL path: the Agent Portal at `/agent` has `state.page: "agent"`. This is not redundant — it is the engine declaring which page it is rendering, and the browser's address bar is one faithful projection of that declaration.

---

## 4. The Affordance Contract

Affordances are the mechanism by which faithful projection guarantees human-agent parity. The contract is:

**Every action a participant can take is represented by an affordance. Every affordance is represented by an interactive element in the human projection.**

This is bidirectional:

- **Agent → Human.** If an agent can `POST /agent/create-cr/a3f7c2d1/title` with `{"value": "My CR"}`, the human sees a text input pre-filled with the current title and a Set button whose tooltip reads `POST /agent/create-cr/a3f7c2d1/title {"value": "My CR"}`. The human can execute the same action through the UI.

- **Human → Agent.** If the human sees a "Delete" button, there is a corresponding affordance with `method: "POST"` and `url: ".../delete"`. The agent can execute the same action via the API.

There is no action that exists only in the UI. There is no action that exists only in the API. The affordance list is the single source of truth for what is possible, and both projections render it faithfully.

### 4.1 Affordance Shapes

The engine produces three affordance shapes, each projected differently by the human renderer:

**Value affordances** have `body: {"value": "<value>"}` and correspond to fields. The renderer projects them inline with the field they modify:

- **Text fields** — a text input pre-filled with the current value, plus a Set button.
- **Select fields (few short options)** — a row of buttons with the current value highlighted.
- **Select fields (many or long options)** — a dropdown with the current value selected, plus a Set button.

**Action affordances** have `body: {}` or no value key. They correspond to lifecycle transitions: Proceed, Go back, Submit, Start a new instance. The renderer projects them as buttons in an Actions bar.

**Navigation affordances** have `method: "GET"`. They correspond to links — opening an instance, viewing a resource. The renderer projects them as anchor elements.

### 4.2 Tooltips as Audit Trail

Every interactive element in the human projection displays its full HTTP request on hover: the method, the URL, and the body. This serves two purposes:

1. **Transparency.** The human can see exactly what action will be performed. There is no hidden behavior behind a button click.
2. **Parity verification.** An engineer can hover over any button and confirm that the request matches what an agent would send. If the tooltip shows a different URL or body than the affordance in the JSON payload, the projection is unfaithful.

For text inputs, the tooltip updates dynamically as the user types, reflecting the actual body that will be sent.

### 4.3 Error Feedback

When an action fails, the engine returns a feedback object with `outcome.error`. The human renderer projects this as a red error banner below the current node title. The agent receives the same error in the JSON response. Both participants see the same failure for the same reason.

---

## 5. Page-Specific Renderers

Faithful projection does not require a universal renderer. Different pages have different semantic shapes — a portal is a collection index, a workflow instance is a form with fields and topology, a quality manual is a document browser. Each shape warrants its own renderer.

What faithful projection requires is that **whatever renderer serves a page type is a faithful projection of the GET payload**. The portal renderer reads `state.workflows`, `instructions`, and `affordances` and builds a card grid. The workflow renderer reads `state.fields`, `state.node`, `instructions`, and `affordances` and builds a form with inline controls. Both are faithful. Neither invents content. Neither omits content.

The shared conventions that make the system coherent:

- Every payload has `{state, instructions, affordances}`.
- Affordances always have `id`, `label`, `method`, `url`.
- POST affordances have `body`.
- Select affordances have `parameters.value.options`.
- The Human/Agent toggle switches between the rendered projection and the raw JSON.
- The Full/Feedback toggle switches between current state and last action feedback.

These conventions are the grammar. The renderers are the dialects.

### 5.1 The Purple Border

In the current implementation, a purple border delineates the renderer's territory on every page. Everything inside the border is the renderer's projection of the GET payload. Everything outside — the sidebar, the layout, the toggle buttons — is the base template's responsibility. This visual convention makes the semantic-representational boundary visible during development.

---

## 6. The Two Projections

The system currently supports two projections of every page:

**Human** — a visual renderer that presents state as styled fields, instructions as prose, and affordances as interactive controls (text inputs, buttons, dropdowns). This is the projection optimized for human comprehension and interaction.

**Agent** — a raw JSON renderer that presents the canonical payload as formatted text. This is the projection optimized for machine consumption, debugging, and LNARF auditing. It is also the reference projection: if the Human renderer disagrees with the Agent renderer, the Human renderer is wrong.

Both projections are available on every page via a toggle button. The Human projection is the default. The Agent projection is the audit tool.

### 6.1 The Agent Projection as Ground Truth

The Agent projection (raw JSON) has a special role: it is the trivially faithful projection. It renders every semantic element (lossless) by displaying the entire payload. It invents nothing (non-additive) because it renders the payload verbatim. It exercises representational freedom only in the choice of indentation and syntax highlighting.

Any discrepancy between the Human projection and the Agent projection is, by definition, a faithfulness violation in the Human projection. The Agent projection cannot be unfaithful because it is the payload itself. This makes the toggle button a built-in audit tool: switch to Agent, inspect the payload, switch back to Human, verify that every element appears.

---

## 7. Parity by Construction

The traditional approach to human-agent parity is to build a human UI, then build an API, then write tests that verify they behave the same way. This is parity by verification — you build two systems and check that they agree.

Faithful projection achieves parity by construction. There is one engine, one payload, and multiple projections. The human and the agent consume the same payload. The human's interactive controls execute the same affordances the agent would POST. There is no separate "UI logic" that could drift from the "API logic" because there is no separate logic. The engine computes; the projections render.

This eliminates an entire class of bugs: the class where the UI does something the API doesn't, or vice versa. A confirmation dialog that exists only in the UI is a faithfulness violation — the agent doesn't get a confirmation step, so the human shouldn't either. A URL that exists only in the API is a faithfulness violation — the human can't navigate there, so the agent's affordance is lying. These bugs are not caught by tests; they are prevented by architecture.

### 7.1 The Audit Protocol

Faithfulness can be verified mechanically:

1. `GET` the page URL with `Accept: application/json`. Record the payload.
2. For every element in `state`: verify it appears in the Human projection.
3. For every element in `affordances`: verify a corresponding interactive element exists in the Human projection.
4. For every interactive element in the Human projection: verify it traces to an affordance.
5. For every text element in the Human projection: verify it traces to `state` or `instructions`.

Steps 2-3 test losslessness. Steps 4-5 test non-additivity. If both pass, the projection is faithful.

This protocol was applied to the Agent Portal during development and caught five losses and two additions, all of which were fixed. The protocol is repeatable and should be applied to each new renderer.

---

## 8. Implications for Future Development

### 8.1 New Pages

Adding a new page to the system requires:

1. An engine function that computes the canonical `{state, instructions, affordances}` payload.
2. A route that serves the payload (JSON for agents, HTML for browsers via content negotiation).
3. A page-specific renderer (JavaScript) that faithfully projects the payload.
4. An LNARF audit confirming faithfulness.

The renderer never calls the engine. It never queries the database. It never computes state. It receives a payload and renders it. This separation means new pages can be built without understanding engine internals — only the payload shape matters.

### 8.2 New Affordance Types

When the engine gains a new affordance shape (e.g., file upload, multi-select, rich text), the renderer needs a new interactive control for that shape. But the control is purely representational — it reads the affordance's parameters and body template, presents an appropriate UI, and POSTs the result. The engine change is sufficient to make the capability available; the renderer change determines how it looks.

### 8.3 New Projections

Adding a new projection (e.g., a mobile renderer, an accessibility-focused renderer, a CLI renderer) requires no engine changes. The new projection consumes the same GET payload and exercises the same representational freedom within the same faithfulness constraints. The engine does not know how many projections exist.

### 8.4 The QMS Connection

In a GMP-inspired quality management system, the properties of faithful projection map directly to compliance requirements:

- **Lossless** ensures that no participant is denied information the system considers relevant. An auditor reviewing a workflow sees the same gates, constraints, and affordances as the operator executing it.
- **Non-additive** ensures that no participant perceives state the system doesn't know about. A validation rule that exists only in the UI is an uncontrolled process — it hasn't been through change control, because the engine doesn't know it exists.
- **Representationally free** ensures that the system can present information appropriately for different contexts — a detailed card view for operators, a compact banner for dashboards, a raw payload for automated compliance checks — without any of them diverging from the truth.

The faithful projection architecture doesn't just support the QMS; it embodies the QMS principle that controlled systems should have a single source of truth with traceable, complete, and honest representations.
