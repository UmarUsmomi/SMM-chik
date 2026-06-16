# Scope: Modernization (Threshold 500)

## Architecture
- `smm_engine/content/adapter.py` manages text parsing, quote extraction, and adapters.
- `tests/test_new_features.py` exercises adapters and quote threshold logic.
- Background generation uses Hugging Face, Pollinations, and Cloudflare Workers AI.
- `scratch/` holds utility/testing scripts.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Exploration | Inspect adapter, tests, and AI background generators | none | DONE |
| 2 | Implementation | Change threshold to 500, update tests, create test_ai_generators.py, update .env.example | 1 | DONE |
| 3 | Verification | Review and execute tests and AI scripts, run forensic audit | 2 | DONE |

## Interface Contracts
- Threshold for long news in `smm_engine/content/adapter.py` is 500 characters.
- `scratch/test_ai_generators.py` should be executable standalone and report statuses of the three AI backends.
