# Original User Request

## Follow-up — 2026-06-12T14:29:39Z

You are the Project Orchestrator.
Your working directory is: d:\SMM\.agents\orchestrator_modernization
Your task is to implement the user request detailed in `d:\SMM\ORIGINAL_REQUEST.md` under the "## Follow-up — 2026-06-12T14:29:39Z" header.

Key Requirements:
1. R1: Clean up HUD graphics (remove coordinate grid lines & labels and central concentric reticle & crosshairs, leave borders, circuit paths, border ticks) in `_draw_tech_graphics()`.
2. R2: Remove LoremFlickr, Unsplash, and AI Horde from background generators. Fallback chain: HuggingFace -> Pollinations.ai -> Cloudflare. If fails -> procedural gradient. Update video_generator.py and telegram_pub.py to use `generate_ai_background()` instead of `fetch_background()`.
3. R3: Publish original news image without cover text if available.
4. R4: Remove watermarks `/ игры ⚡ патчи /`.
5. R5: Russo One font usage, auto-download from Google Fonts, and Cyberpunk HUD card with neon vertical indicator.
6. R6: Add `blockquote` selectively (50-70% of posts) only for long articles.
7. R7: Fix scheduler in `bot/app.py` using `last_pipeline_run` database settings to avoid repeated runs on Render.com restarts.
8. Ensure all 51+ tests pass and no warnings.

Follow the standard orchestration protocol:
- Create `plan.md`, `progress.md`, and `context.md` in your working directory.
- Dispatch tasks to appropriate subagents (explorer, worker, reviewer) under separate directories in `.agents/`. Do not write code directly.
- Verify everything by running tests (`python -m pytest`).
- Once finished, write a final handoff report in your folder and report completion.
