# qms-workflow-engine

Unified workflow engine and web UI for QMS agent orchestration.

## Overview

A declarative workflow runtime that interprets YAML workflow definitions and exposes them simultaneously to AI agents (via a resource-oriented API) and to humans (via a real-time observer UI). The engine provides:

- **Content primitives** — Fields (text, boolean, select, computed), Tables (typed columns, construction/execution lifecycle), Lists (ordered collections with CRUD)
- **Control-flow primitives** — Sequential proceed, Routers (automatic conditional branching), Forks (parallel branches), Merges (convergence)
- **Expression language** — Unified evaluator for gates, visibility, navigation guards, acceptance criteria, router conditions (AND/OR/NOT composites)
- **Affordance-driven interaction** — Self-describing action specifications generated fresh on every render
- **Structured feedback** — POST returns a diff of outcome, cascading effects, and new affordances
- **Pluggable observation** — Multiple renderers consuming the same page dictionary via SSE

All code lives in `wfe-ui/`. See `wfe-ui/ENGINE.md` for the full engine reference and `wfe-ui/TAXONOMY.md` for the primitive catalog.

## Relationship to pipe-dream

This repository is a submodule of [pipe-dream](https://github.com/whharris917/pipe-dream), the parent project that houses the QMS (Quality Management System) and the Flow State application. Development of this engine is governed by the QMS change control process.
