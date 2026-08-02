# Production-readiness tasks

## Phase 1 — Baseline and inventory

- [x] Record repository, branch, and unrelated working-tree state.
- [x] Run the full pytest baseline and Python compile check.
- [x] Inventory every HTTP route, trust boundary, external integration, and deployment path.
- [x] Verify local SQLite integrity, tables, indexes, and representative read paths.
- [x] Inspect dependency versions and CI/deployment configuration for concrete risks.

## Phase 2 — Security hardening

- [x] Add failing regression tests for unauthenticated administrative access in production.
- [x] Make dashboard/API authentication fail closed in production and compare credentials safely.
- [x] Add failing regression tests for webhook authorization and sensitive logging behavior.
- [x] Harden webhook validation, payload handling, and logs without breaking Telegram delivery.
- [x] Check tracked files and pending diffs for credentials or deployment secrets.

## Checkpoint — Security

- [x] Focused security tests pass.
- [x] Full test suite and compile check pass.
- [x] Manual review finds no reachable critical/high issue.

## Phase 3 — Reliability and database

- [x] Add a readiness check that validates the database without exposing details.
- [x] Test connection cleanup and health behavior on success and dependency failure.
- [x] Audit scheduler and pipeline concurrency/error reporting; fix confirmed defects only.
- [ ] Verify SQLite locally and production PostgreSQL read-only after deployment.

## Checkpoint — Runtime

- [x] Local server starts from the documented command.
- [x] Health/readiness, queue, and protected actions behave as specified.
- [x] Full tests remain green.

## Phase 4 — Browser product audit

- [x] Test the local dashboard at desktop and mobile viewport widths.
- [x] Inspect page accessibility, console errors, failed network requests, and core operator flow.
- [x] Implement and regression-test the smallest high-impact UX fixes found.
- [x] Re-run local browser smoke tests.

## Phase 5 — Deploy and verify

- [x] Identify the existing Obsidian production service and its current revision.
- [x] Review deployment environment/settings without revealing secret values or choosing paid options.
- [x] Run final tests, compile, dependency/config audit, and code review.
- [ ] Commit only intended project files; keep unrelated staged `gh.exe` separate.
- [ ] Push the current branch and deploy through the existing free service.
- [ ] Smoke-test production UI, liveness/readiness, authentication, logs, and database connectivity.
- [ ] Record deployed revision, verification evidence, known limitations, and rollback procedure.

## Definition of done

- [ ] All success criteria in `implementation_plan.md` are demonstrated by tests or live checks.
- [ ] No paid subscription or destructive production operation was performed.
- [ ] No required work remains, or a genuine external blocker has repeated across three goal turns.
