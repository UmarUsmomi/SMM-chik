## 2026-06-12T14:38:57Z
You are the worker subagent (teamwork_preview_worker) for Milestone 3 (BG Generators & Bypass) of the SMM bot modernization project.
Your working directory is: d:\SMM\.agents\worker_m3\
Your task is to implement the following changes:

1. **R2: Update background generators in `smm_engine/media/image_handler.py`**
   - Delete the `fetch_background()` method entirely.
   - Delete the `generate_horde_background()` method entirely.
   - Update `generate_ai_background()` to route through: HuggingFace -> Pollinations.ai -> Cloudflare Workers AI.
   - If all three generators fail, it must fall back to the procedural gradient. Generate the procedural gradient using `self._generate_procedural_background()`, save it to a temp file path in `self.temp_dir` (e.g. `self.temp_dir / ("procedural_fallback_v.jpg" if vertical else "procedural_fallback.jpg")`), and return that file path.
   - Make sure no comments, strings or code references to `LoremFlickr`, `Unsplash`, or `AI Horde` remain in `image_handler.py`.

2. **R2: Update background generators usage**
   - In `smm_engine/media/video_generator.py` (around line 43):
     Replace:
     `bg_path = await self.image_gen.fetch_background(bg_keywords, vertical=True)`
     with:
     `bg_path = await self.image_gen.generate_ai_background(bg_keywords, vertical=True)`
   - In `smm_engine/publishers/telegram_pub.py` (around line 450):
     Replace:
     `bg_path = await img_gen.fetch_background(keywords)`
     with:
     `bg_path = await img_gen.generate_ai_background(keywords)`

3. **R3: Publish original news image without cover text**
   - In `publish_post_with_cover()` of `smm_engine/publishers/telegram_pub.py`:
     - When `image_url` is present and `bg_path = await img_gen.download_image(image_url)` successfully returns a valid file path, set a flag `is_original_image = True`.
     - If `is_original_image` is True, bypass the `img_gen.create_cover(title, bg_path)` step and set `cover_path = bg_path`.
     - Otherwise, if we fall back to AI generated background, run `cover_path = img_gen.create_cover(title, bg_path)` as before.
     - When unlinking temp files, ensure we only delete `cover_path` if it exists, and delete `bg_path` only if `bg_path` is not the same as `cover_path`. E.g.:
       ```python
       try:
           if cover_path and cover_path.exists():
               cover_path.unlink()
           if bg_path and bg_path.exists() and bg_path != cover_path:
               bg_path.unlink()
       except Exception as e:
           logger.warning(f"Failed to delete temp cover files: {e}")
       ```

4. **Update/fix tests in `tests/test_new_features.py`**
   - Delete the `test_loremflickr_url_format()` test completely.
   - In `test_ai_background_routing()`, update the patches and assertions:
     - Remove patches/assertions for `generate_horde_background`.
     - Test the fallback routing of `generate_ai_background`: HuggingFace -> Pollinations.ai -> Cloudflare Workers AI -> procedural gradient. You can patch `generate_hf_background`, `generate_pollinations_background`, and `generate_cloudflare_background` to return fake paths/None and verify `generate_ai_background` behaves correctly.
   - If there is any other test calling `fetch_background()` (e.g. at line 402, check if any remains after deleting `test_loremflickr_url_format`), replace it with `generate_ai_background()`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

After editing the code, run local unit tests using pytest to verify.
Write a report of your changes and test results to `d:\SMM\.agents\worker_m3\handoff.md` and send a message back to the orchestrator (conversation ID: 729f88fb-0e2a-4076-886d-f90f3c5b847e).
