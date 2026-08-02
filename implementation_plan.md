# Production-readiness plan: SMM Automator

## Objective

Turn the existing FastAPI/Telegram SMM automation service into a safe, observable,
reliably deployable product. The primary operator must be able to inspect the queue,
moderate posts, run the pipeline, and verify service/database health without exposing
administrative actions to anonymous visitors or exceeding free service quotas.

## Current architecture

- Python 3.11+ application with FastAPI in `bot/app.py`.
- Content pipeline and external integrations in `smm_engine/`.
- SQLite for local development and PostgreSQL through `DATABASE_URL` in production.
- Server-rendered dashboard in `web/templates/index.html`.
- Render-compatible web process via `Procfile` and scheduled GitHub Actions.
- Pytest unit/integration suite in `tests/`; `npm test` selects the available Python.

## Commands

- Full tests: `npm test -- -q -p no:cacheprovider`
- Compile check: `.\\.tools\\Python312-embed\\python.exe -m compileall -q smm_engine bot`
- Local server: `.\\.tools\\Python312-embed\\python.exe scripts/run_server.py`
- Git status: `git status --short --branch`

## Product requirements

1. Public liveness checks remain available without credentials.
2. Dashboard pages and state-changing dashboard APIs require configured, constant-time
   authentication in production. Missing production credentials fail closed.
3. Telegram webhooks require their configured secret in production and do not log full
   user payloads or secrets.
4. Database connections close at request/task boundaries; the schema initializes safely
   on SQLite and PostgreSQL; health reporting distinguishes liveness from dependency health.
5. Pipeline runs cannot overlap within one process and failures are visible to operators.
6. The UI renders without browser console errors, works at desktop/mobile widths, and
   exposes honest loading, empty, success, and failure states.
7. Deployment configuration starts cleanly, carries no committed secrets, uses no paid
   feature, and has a documented rollback path.

## Testing strategy

- Reproduce each confirmed defect with a focused pytest test before changing behavior.
- Run the focused test after each small change and the full suite at checkpoints.
- Exercise health, authentication, queue, moderation, and pipeline controls through a real
  browser against both the local server and the deployed service.
- Inspect browser console/network failures and verify database integrity/schema read-only.
- Run dependency/configuration and secret-leak checks before any push.

## Boundaries

- Always: preserve unrelated user changes; parameterize SQL values; close database
  connections; redact credentials; keep health checks side-effect free; verify every change.
- May do autonomously: add regression tests, harden existing routes, improve error handling,
  update free deployment configuration, push the current feature branch, and deploy through
  an already-connected free service.
- Ask first: destructive production data operations, schema changes that cannot be rolled
  back, changing the intended operator workflow, or enabling any paid service/tier.
- Never: commit `.env` or credentials, reveal secret values in output, buy/subscribe to a
  plan, disable failing tests, delete production data, or overwrite unrelated staged work.

## Implementation order

1. Baseline and inventory: tests, compile, routes, dependencies, database, deployment state.
2. Security slice: fail-closed admin authentication, webhook authorization, safe logging,
   security regression tests.
3. Reliability slice: health/readiness, database lifecycle/integrity, scheduler/pipeline
   error behavior, regression tests.
4. Product slice: browser audit and the smallest high-impact dashboard UX/accessibility fixes.
5. Delivery slice: full quality/security review, push, free deployment, production smoke
   tests, database verification, rollback notes.

## Risks and mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Existing deployment credentials are only in a signed-in browser/provider | High | Use the requested Browser/Computer surfaces; never extract or print credentials. |
| Free Render instance sleeps or has ephemeral disk | High | Treat `/health` as liveness, use PostgreSQL for durable production state, allow warm-up. |
| Automatic publishing causes an unintended public post | High | Browser/API smoke tests must not trigger publish; use mocks locally and read-only checks in production. |
| Current staged `gh.exe` is unrelated user work | Medium | Do not modify, unstage, or include it in project commits. |
| External AI/Telegram APIs have quotas | Medium | Prefer local tests and metadata/status calls; do not create paid usage or subscriptions. |

## Success criteria

- Full automated suite and compile checks pass after all edits.
- No critical/high security finding remains in reachable production paths.
- Local browser smoke tests pass with no relevant console/network errors.
- Deployed service returns healthy liveness/readiness responses and protected admin routes.
- Production database connectivity and expected tables are verified without destructive writes.
- The reviewed commit is pushed and the deployed revision is confirmed through a final smoke test.

## Open questions resolved during audit

- Deployment provider/URL: discover from repository metadata and existing signed-in browser.
- Production database provider: discover from deployment settings without exposing values.
- Product name “Obsidian”: verify from the live page rather than assuming it means the desktop app.
