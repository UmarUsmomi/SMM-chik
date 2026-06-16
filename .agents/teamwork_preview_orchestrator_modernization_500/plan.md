# Plan — Modernization and Verification (Threshold 500)

This plan documents the step-by-step path to implement the requirements under `## Follow-up — 2026-06-13T13:55:59Z`.

## Requirements Reference
- **R1**: Lower the news length threshold for quotes to 500 characters in `smm_engine/content/adapter.py`, and update the corresponding tests in `tests/test_new_features.py`.
- **R2**: Create a testing script `scratch/test_ai_generators.py` to independently check Hugging Face, Pollinations, and Cloudflare Workers AI. Report status, response times, key availability in `.env`, and save output images in `temp_media/`.
- **R3**: Update `.env.example` to document `HUGGINGFACE_API_KEY`.

## Phases

### Phase 1: Exploration & Analysis
1. Spawn `teamwork_preview_explorer` to inspect `smm_engine/content/adapter.py` and `tests/test_new_features.py` to locate the current threshold.
2. Locate existing integrations for Hugging Face, Pollinations, and Cloudflare Workers AI in the codebase.
3. Verify directory layout and where `temp_media/` is located.
4. Produce an exploration report with detailed implementation recommendations.

### Phase 2: Implementation
1. Spawn `teamwork_preview_worker` with domain expertise.
2. Modify `smm_engine/content/adapter.py` to lower the quote length threshold from 800 to 500.
3. Update `tests/test_new_features.py` to test the new threshold.
4. Create `scratch/test_ai_generators.py` conforming to requirements:
   - Check key availability in `.env`.
   - Call Hugging Face, Pollinations, and Cloudflare Workers AI independently.
   - Record response times and status (success/error).
   - Save generated images to `temp_media/`.
   - Print details clearly to stdout.
5. Add `HUGGINGFACE_API_KEY` to `.env.example`.
6. Run `pytest` to verify all tests pass.

### Phase 3: Review & Verification
1. Spawn `teamwork_preview_reviewer` to review changes and run tests.
2. Spawn `teamwork_preview_challenger` to verify `scratch/test_ai_generators.py` output and behavior.
3. Spawn `teamwork_preview_auditor` to run integrity checks.

### Phase 4: Synthesis & Handoff
1. Synthesize findings from subagents.
2. Report success to the main agent.
