# qms-workflow-engine

Graph-based workflow engine for QMS agent orchestration.

## Overview

A DAG-based workflow engine built on three bedrock primitives:

- **Slot** — `{name, type, value?, writable}` — the atomic unit of data
- **Node** — `{id, slots, edges, prompt?}` — a step in a workflow
- **Edge** — `{to, when?}` — a conditional connection between nodes

Everything else — prompts, schemas, gates, templates, documents — is emergent from these three primitives.

## Relationship to pipe-dream

This repository is a submodule of [pipe-dream](https://github.com/whharris917/pipe-dream), the parent project that houses the QMS (Quality Management System) and the Flow State application. Development of this engine is governed by the QMS change control process.

## Status

Under development. Governed by QMS change control from commit zero.
