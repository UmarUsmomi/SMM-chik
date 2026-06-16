## 2026-06-12T14:43:01Z

You are the worker subagent (teamwork_preview_worker) for Milestone 4 (Quotes & Scheduler) of the SMM bot modernization project.
Your working directory is: d:\SMM\.agents\worker_m4\
Your task is to implement the following changes:

1. **R6: Add blockquote selectively in `smm_engine/content/adapter.py`**
   - In `_adapt_pass()` (around line 75):
     - Extract the full content string from the news item:
       ```python
       content_str = item.raw_data.get("content") or item.raw_data.get("description") or item.raw_data.get("summary") or ""
       ```
     - Determine if it is a long article: `is_long = len(content_str) > 800`.
     - Decide selectively (with a 60% probability) whether to allow a blockquote:
       ```python
       import random
       allow_blockquote = is_long and (random.random() < 0.60)
       ```
     - Define the prompt instruction dynamically based on `allow_blockquote`:
       - If `allow_blockquote` is True, use the standard instruction:
         `"- Если в новости есть яркая прямая цитата эксперта или разработчика, оформи её тегом <blockquote expandable>текст цитаты</blockquote>. Используй цитаты только при наличии реальной цитаты в источнике, не придумывай их!"`
       - If `allow_blockquote` is False, use:
         `"- КАТЕГОРИЧЕСКИ ЗАПРЕЩАЕТСЯ использовать тег <blockquote> или <blockquote expandable> в этом поста. Все цитаты должны быть перефразированы простым текстом."`
     - Interpolate this instruction into the Gemini prompt dynamically.

2. **R7: Fix Render.com scheduler in `bot/app.py`**
   - In `scheduler_loop()` (lines 45-64):
     - Retrieve `last_pipeline_run` from the database. Since `DatabaseManager` is already imported and instantiated, use the `db` instance from `bot.app` or instantiate `db = DatabaseManager()`.
     - If the setting exists, parse it: `last_run = datetime.fromisoformat(last_run_str)`. Make it timezone-aware if needed.
     - Calculate elapsed time since the last run. If `elapsed < interval_seconds`, compute `remaining = interval_seconds - elapsed`. Log that the pipeline ran recently and sleep for `remaining` seconds (using `await asyncio.sleep(remaining)`), then continue the loop.
     - When a run starts (or completes), update the database setting with the current time in ISO format:
       `db.set_setting("last_pipeline_run", datetime.now(timezone.utc).isoformat())`
       Make sure to import `timezone` and `datetime`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

After editing the files, write unit tests to verify both features if possible (or run the test suite to ensure no regressions).
Write a report of your changes and test results to `d:\SMM\.agents\worker_m4\handoff.md` and send a message back to the orchestrator (conversation ID: 729f88fb-0e2a-4076-886d-f90f3c5b847e).
