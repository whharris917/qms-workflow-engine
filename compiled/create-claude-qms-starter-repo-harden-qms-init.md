# create-claude-qms-starter-repo-harden-qms-init

### Change Overview

**Title:** Create claude-qms Starter Repo, Harden qms init

**Purpose:** End users have no canonical way to obtain the QMS framework. qms init currently unpacks seed/ into whatever directory it is run from with no guard beyond collision checks and no confirmation. This CR creates claude-qms as the canonical distribution repo and hardens qms init with marker-based targeting and a confirmation prompt.

**Scope:** qms-cli: redesign qms init (marker detection, confirmation prompt, --yes flag, --root marker placement, no-context error). New repo: whharris917/claude-qms with .claude-qms marker, qms-cli submodule, README.md. SDLC-QMS-RS/RTM update. SDLC-CQ namespace registration.

### Execution Items

| Task Description | Vr Required | Execution Summary | Outcome | Performed By | Date | Child Workflows |
| --- | --- | --- | --- | --- | --- | --- |
| Pre-execution baseline commit | False | [READY] | [READY] | [READY] | [READY] | outcome==Fail: [VAR](compiled/var.md) |
| Set up development environment for qms-cli | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Check out and update the Requirements Specification (RS) for qms-cli | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Implement the change on the development branch | True | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md), vr_required==True: [VR](compiled/vr.md) |
| Qualify the implementation (all tests pass, CI green on branch) | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Verify integration in test environment | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Update the Requirements Traceability Matrix (RTM) — reference execution branch commit hash | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Open PR against qms-cli main branch and merge (no-ff, squash prohibited) | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Update qms-cli submodule pointer in pipe-dream | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Post-execution baseline commit | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Create whharris917/claude-qms on GitHub: .claude-qms marker, qms-cli submodule, README.md, .gitignore; push | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Register SDLC namespace CQ; create initial SDLC-CQ-RS and SDLC-CQ-RTM; route for review and approval | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Update qms-cli submodule pointer in claude-qms after merge; push | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Update sandbox/launch.sh to clone claude-qms and run qms init --yes | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |
| Verify sandbox end-to-end: clone claude-qms, run qms init, run qms commands, confirm all artifacts created | False | [BLOCKED] | [BLOCKED] | [BLOCKED] | [BLOCKED] | outcome==Fail: [VAR](compiled/var.md) |

---