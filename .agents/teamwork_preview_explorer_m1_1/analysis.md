# Analysis & Implementation Plan: Branded Watermark Rendering (R1)

## Executive Summary
This document analyzes and designs the implementation of branded watermark rendering (R1) in the bottom-right corner of both square (1080x1080) and vertical (720x1280) covers. The rendering logic uses theme-configured parameters from `themes/*.yaml`, specifically `text_parts`, `font_size`, and colors (`watermark_text` and `watermark_accent`), utilizing the Montserrat-Bold font. To guarantee perfect readability on any AI-generated or custom background, we propose a semi-transparent HUD-style backing card with an optional text outline.

---

## 1. Codebase & Configuration Analysis

### 1.1 Theme Configurations (`themes/*.yaml`)
We inspected `themes/default.yaml`, `themes/cyberpunk.yaml`, and `themes/dracula.yaml`. All follow a unified structure for watermark configuration:

- **Colors Section**:
  - `watermark_text`: The base color for watermark text segments (usually white/cyan/gray matching `text_primary`).
  - `watermark_accent`: The highlight color for accent segments like icons or special symbols (e.g. `[217, 4, 41, 255]` red or `[252, 238, 10, 255]` neon yellow, matching `brand_accent`).
- **Watermark Section**:
  - `font_size`: Font size for the watermark (typically `24`).
  - `text_parts`: A list of dictionaries defining the string segments to be printed sequentially.
    - `text`: Segment text (e.g. `"/ игры "`, `"⚡"`, `" патчи /"`).
    - `color_type`: Either `"primary"` or `"accent"`.

### 1.2 Target Image Generator (`smm_engine/media/image_handler.py`)
- **Font Access**: `ImageGenerator` downloads or bundles `fonts/Montserrat-Bold.ttf` under `self.font_path`.
- **Theme Loading**: `_load_theme()` loads the YAML based on the environment variable `BRANDING_THEME` (lowercased) and provides a fully structured hardcoded fallback.
- **Image Formats**:
  - **Square covers**: `1080` x `1080` pixels.
  - **Vertical covers**: `720` x `1280` pixels.
- **Layout Margins**:
  - Inner HUD border offset is `offset = 24`.
  - Headline text ends at `y_start = height - total_text_height - 80`. The space below `height - 80` is left completely clear, making it the perfect zone for the watermark.

---

## 2. Watermark Rendering Design

### 2.1 Positioning and Bounding Box
To align perfectly with the tech-HUD styling, the watermark should sit in the bottom-right corner, inside the inner border (`offset = 24`) with an additional `16px` padding:
- `x_end = width - offset - 16`
- `y_end = height - offset - 16`

We calculate the width of each text segment using `ImageFont.getlength(text)` or a fallback. The total width is `total_wm_width = sum(segment_widths)`.
The height is calculated using the font metrics `ascent + descent` or defaults to `font_size`.
This places the starting coordinate of the watermark at:
- `wm_x_start = x_end - total_wm_width`
- `wm_y_start = y_end - wm_height`

### 2.2 Readability Backing Designs

We analyzed three readability techniques:
1. **Semi-transparent HUD Backing Card (Primary)**:
   - Draw a rounded rectangle card layer behind the text using theme colors:
     - Fill: `brand_dark` with `180` opacity (~70% opaque).
     - Outline: `brand_accent` with `80` opacity (~30% opaque).
   - Card bounds: padded by `12px` horizontally and `6px` vertically around the text.
   - This provides perfect readability against any high-contrast background and fits the HUD badge theme.
2. **Text Outline (Complementary/Alternative)**:
   - Draw the text using Pillow's `stroke_width=1` and `stroke_fill=brand_dark` (solid).
   - This ensures character edge separation and works well with or without the card backing.
3. **Text Glow / Soft Shadow**:
   - Draw the text offset in multiple directions before printing the primary colored text. This acts as a fallback or extra level of contrast.

### 2.3 Color Resolving Logic
To handle any missing configuration keys robustly, we use the following fallback chain:
- **Primary Segments**: `colors.get("watermark_text")` $\rightarrow$ `colors.get("text_primary")` $\rightarrow$ `[255, 255, 255, 255]`
- **Accent Segments**: `colors.get("watermark_accent")` $\rightarrow$ `colors.get("brand_accent")` $\rightarrow$ `[217, 4, 41, 255]`
- **Backing Fill**: `colors.get("brand_dark")` $\rightarrow$ `[13, 15, 20, 255]`
- **Backing Outline**: `colors.get("brand_accent")` $\rightarrow$ `[217, 4, 41, 255]`

---

## 3. Implementation Plan

### Phase 1: Modify `smm_engine/media/image_handler.py`
Add the watermark rendering block to `create_cover` right before the image is saved.
- Use `ImageFont.truetype` to load Montserrat-Bold at `watermark.font_size`.
- Sequentially draw the backing rounded rectangle (with a fallback to standard rectangle for safety).
- Render each segment with its resolved color and a subtle dark stroke.

*(See exact code diff in `watermark_rendering.patch`)*

### Phase 2: Update Tests in `tests/test_media.py`
Add `test_image_generator_watermark` to verify the rendering:
- Mock/Inject a custom watermark config into `img_gen.theme` to check dynamic configuration reading.
- Call `create_cover` with `bg_path=None` to ensure fallback works.
- Verify that the image is created successfully with the correct size.

*(See exact code diff in `test_watermark.patch`)*

### Phase 3: Verify and Run Suite
Once implemented, run `pytest tests/` to confirm that all tests pass without errors.
