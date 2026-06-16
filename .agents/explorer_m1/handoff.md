# Handoff Report — Explorer Milestone 1

## 1. Observation

This section contains direct observations of files, line numbers, and warnings in the `SMM` codebase.

### A. HUD Graphics & Watermark in `smm_engine/media/image_handler.py`
- **`_draw_tech_graphics` Function**:
  - Located at: `smm_engine/media/image_handler.py:418-584`
  - Code segment:
    ```python
    def _draw_tech_graphics(self, draw: ImageDraw.ImageDraw, width: int, height: int, colors: dict):
        """Draws subtle, high-tech graphical HUD elements, coordinate grids, and circuit node paths to fill the background"""
        import math
        brand_accent = tuple(self._parse_color(colors.get("brand_accent"), [217, 4, 41, 255]))
        ...
    ```
- **`create_cover` Function**:
  - Located at: `smm_engine/media/image_handler.py:612-878`
  - It handles cropping backgrounds, applying gradients, drawing inner borders, crop marks, calling `_draw_tech_graphics()`, drawing a title, and rendering the watermark.
- **Watermark Rendering**:
  - Located at: `smm_engine/media/image_handler.py:783-869`
  - It retrieves `wm_config = self.theme.get("watermark", {})` and renders custom text parts (with transparent background bounding boxes and low opacity accent borders) in the bottom-right corner.

### B. Montserrat-Bold Loading and Font Fetching in `smm_engine/media/image_handler.py`
- **`_setup_font` Function**:
  - Located at: `smm_engine/media/image_handler.py:47-67`
  - It checks if a bundled font file exists:
    ```python
    font_file = Path(__file__).resolve().parent.parent.parent / "fonts" / "Montserrat-Bold.ttf"
    if font_file.exists():
        logger.info(f"Using bundled Montserrat-Bold font: {font_file}")
        return font_file
    ```
  - If the bundled font is missing, it performs an HTTP request to download it from:
    `https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf`

### C. Background Generator Logic
- **AI Generators**:
  - HuggingFace API: `generate_hf_background()` (`smm_engine/media/image_handler.py:129-163`)
  - AI Horde: `generate_horde_background()` (`smm_engine/media/image_handler.py:165-217`)
  - Pollinations.ai: `generate_pollinations_background()` (`smm_engine/media/image_handler.py:219-254`)
  - Cloudflare Workers AI: `generate_cloudflare_background()` (`smm_engine/media/image_handler.py:256-298`)
  - AI Routing Chain: `generate_ai_background()` (`smm_engine/media/image_handler.py:300-323`)
- **Stock Generators & Gradients**:
  - LoremFlickr / Unsplash Curated: `fetch_background()` (`smm_engine/media/image_handler.py:324-370`)
  - Procedural Gradient Fallback: `_generate_procedural_background()` (`smm_engine/media/image_handler.py:585-610`)

### D. Usage of `fetch_background()`
- **Video Generator**:
  - Located at: `smm_engine/media/video_generator.py:43`
  ```python
  bg_path = await self.image_gen.fetch_background(bg_keywords, vertical=True)
  ```
- **Telegram Publisher**:
  - Located at: `smm_engine/publishers/telegram_pub.py:450`
  ```python
  bg_path = await img_gen.fetch_background(keywords)
  ```
- **Tests**:
  - Located at: `tests/test_new_features.py:402`
  ```python
  await img_gen.fetch_background("artificial intelligence, glowing brain")
  ```

### E. News Image Downloads & Cover Publishing in `telegram_pub.py`
- **`publish_post_with_cover` Function**:
  - Located at: `smm_engine/publishers/telegram_pub.py:414-472`
  - Section downloading the original news image:
    ```python
    if image_url:
        bg_path = await img_gen.download_image(image_url)
    ```
  - Section rendering final cover:
    ```python
    cover_path = img_gen.create_cover(title, bg_path)
    ```
  - Currently, there is no logic to bypass `img_gen.create_cover(title, bg_path)` to send the raw downloaded news image without text/graphics overlay.

### F. Blockquote Formatting in `smm_engine/content/adapter.py`
- **Adapter Prompt Rules**:
  - Located at: `smm_engine/content/adapter.py:91`
  - Exact prompt instruction:
    `"- Если в новости есть яркая прямая цитата эксперта или разработчика, оформи её тегом <blockquote expandable>текст цитаты</blockquote>. Используй цитаты только при наличии реальной цитаты в источнике, не придумывай их!"`

### G. Scheduler Loop and Database Settings
- **Scheduler Loop**:
  - Located at: `bot/app.py:45-64`
  - Spawns a background task that sleeps 30 seconds, runs the pipeline, then sleeps for `interval_seconds`. Any container restart triggers an immediate execution.
- **Database Settings Methods**:
  - Located at: `smm_engine/storage/database.py:168-200`
  - Uses the `app_settings` table to store and retrieve general string key-value settings.

### H. Warnings in Test Logs
- **`google.generativeai` Warning**:
  - Observed in `scratch/pipeline_utf8.log:9-10`:
    `"All support for the google.generativeai package has ended. It will no longer be receiving updates or bug fixes. Please switch to the google.genai package as soon as possible."`
- **`sqlite3` Datetime Warning**:
  - Python 3.12+ deprecated datetime adapters and converters. Implicit datetime bindings will raise deprecation warnings.

---

## 2. Logic Chain

1. **Obsolete Background Generators**: Since `fetch_background()` uses LoremFlickr and Unsplash, and the requirement states they must be removed, we need to delete `fetch_background()`, remove the Unsplash fallback chain, and instead call `generate_ai_background()` from `video_generator.py` and `telegram_pub.py`.
2. **Watermark Control**: Watermarks are currently unconditionally rendered by `create_cover()`. If watermarks need to be disabled or customized dynamically, we should read a theme flag or parameter (e.g. `show_watermark` or `watermark_enabled`) to decide whether to execute lines 783–869.
3. **Publishing Original News Images**: If an original image was successfully downloaded (`bg_path` exists from `download_image(image_url)`), the publisher currently wraps it in `create_cover()`, generating a text-overlay version. To allow publishing without text overlay, the publisher should bypass `create_cover()` and send `bg_path` directly when it is a downloaded original news image.
4. **Selective Blockquotes**: `adapter.py` instructs Gemini to add blockquotes whenever a quote exists. To make it selective, we must modify this prompt instruction to specify: "only for long/detailed articles, and selectively (50-70% of the time) when it provides meaningful insight."
5. **Render.com Scheduler Loop**: `scheduler_loop()` in `bot/app.py` has no persistent memory of the last run. By checking the `last_pipeline_run` setting in the DB (`db.get_setting("last_pipeline_run")`) and calculating elapsed time on startup, we can avoid redundant pipeline runs during container restarts.
6. **Pytest Baseline**: The test suite contains 51 unit/integration tests across 8 test files. Warnings about `sqlite3` datetime adapters and `google.generativeai` package deprecation can be suppressed in `pyproject.toml` using `filterwarnings` to keep test outputs clean.

---

## 3. Caveats

- We did not run pytest locally since the interactive command approval timed out, but we successfully mapped the entire test suite of 51 tests and identified the warnings based on existing logs (`pipeline_utf8.log`) and standard Python 3.12+ runtime behaviors.
- The `google-generativeai` warning is a FutureWarning; it does not block execution but warns of future library deprecation.

---

## 4. Conclusion

- **Obsolete Backgrounds**: Remove `fetch_background()` from `image_handler.py`. Change calls in `video_generator.py` and `telegram_pub.py` to use `generate_ai_background()`. Remove `test_loremflickr_url_format()` from tests.
- **Original Images**: Modify `telegram_pub.py` to publish the downloaded `bg_path` directly (without calling `create_cover()`) when it originates from the news item URL.
- **Blockquotes**: Update the Gemini prompt in `adapter.py` to apply blockquotes selectively (50-70% frequency) on long articles.
- **Scheduler**: Update `scheduler_loop()` in `bot/app.py` to read/write `last_pipeline_run` from the database.
- **Warnings**: Ensure datetime formatting uses string serialization for SQLite database tasks and suppress deprecation warnings in `pyproject.toml` if they persist.

---

## 5. Verification Method

- **Run Tests**: Execute `python -m pytest` to verify all 51 tests run and pass without warnings.
- **Inspect Database**: Run `python scratch/inspect_db.py` to check that the `last_pipeline_run` setting updates correctly.
- **Verify Logs**: Run the pipeline and review logs in `scratch/pipeline.log` to confirm no warnings are emitted.
