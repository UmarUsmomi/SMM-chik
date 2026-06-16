# Analysis & Implementation Plan: Techno-Gaming Background Generation Prompts

This report details the analysis of the background generation functions in `smm_engine/media/image_handler.py` and proposes optimized, high-contrast, techno-gaming themed prompts for Hugging Face (FLUX.1-schnell) and AI Horde.

---

## 1. Analysis of Current Background Generation

### Current Functions

The background image generation in `smm_engine/media/image_handler.py` relies on two main APIs:
1. **Hugging Face Serverless Inference API** (`generate_hf_background`):
   - **Model**: `black-forest-labs/FLUX.1-schnell`
   - **Current Prompt**:
     ```python
     prompt = f"cyberpunk synthwave hacker matrix code rain background {clean_keywords}, masterpiece, highly detailed, neon lights"
     ```
2. **AI Horde API** (`generate_horde_background`):
   - **Model**: Default (typically various Stable Diffusion 1.5/XL models hosted by Horde workers)
   - **Current Prompt**:
     ```python
     prompt = f"cyberpunk matrix code rain glowing background {clean_keywords}, high resolution, hacker synthwave aesthetic"
     ```

### Identified Weaknesses & Limitations

1. **Lack of Text-Safe Negative Space (Title Readability)**:
   The PIL drawing engine overlays the news headline at the bottom of the image starting at:
   $$y\_start = height - total\_text\_height - 80$$
   This corresponds to the bottom 40-50% of the image. The current prompts do not control image composition. As a result, the AI often generates bright, high-contrast details in the lower half of the image. Even with a semi-transparent black gradient overlay (`overlay_dim`), this results in busy background noise that degrades text readability.
2. **FLUX.1-schnell Prompt Structure Under-utilization**:
   FLUX.1-schnell is a state-of-the-art flow-matching transformer model. It responds far better to detailed, natural-language, descriptive scenes than to comma-separated tag lists ("masterpiece, highly detailed, neon lights").
3. **Missing AI Horde Negative Prompts**:
   AI Horde generates using Stable Diffusion models, which frequently hallucinate gibberish text, logos, or signatures. The current prompt lacks a negative prompt. AI Horde natively parses `###` inside the prompt parameter to separate positive prompts from negative prompts.
4. **Coordination with PIL HUD Elements**:
   The generator procedurally draws HUD reticles around `cy = int(height * 0.38)` (upper-middle area) and tech grids and circuits (`_draw_tech_graphics`). If the AI background also places massive bright elements in those exact spots, the graphics overlap and create clutter. The prompt must instruct the generator to produce clean, atmospheric backgrounds that act as a *canvas* rather than a competing graphic.

---

## 2. Optimized Prompt Designs (Techno-Gaming Aesthetic)

### Hugging Face: FLUX.1-schnell
FLUX.1-schnell excels at layout-based instructions, sharp light physics, and complex scene composition. We structure the prompt as a descriptive, natural language paragraph emphasizing top/bottom composition.

**Proposed Prompt Template**:
```python
prompt = (
    f"A dark, high-contrast techno-gaming background featuring {clean_keywords}. "
    "The composition is vertically split: the upper half contains glowing cyberpunk neon accents, "
    "digital HUD wireframes, and intricate circuit lines in electric cyan and vibrant red. "
    "The lower half is a clean, dark negative space with deep black shadows and minimal gradients. "
    "Futuristic gaming aesthetic, clean digital render, synthwave mood, dramatic atmospheric lighting, "
    "sharp details in the upper section, 8k resolution. No text, letters, or watermark."
)
```

**Why it works**:
- **Spatial Control**: Instructs FLUX to place detailed neon highlights in the upper half and keep the lower half dark.
- **Color Accents**: Replaces generic "neon lights" with "electric cyan and vibrant red" to match the default theme accents.
- **Style Cohesion**: Incorporates "gaming aesthetic" and "HUD wireframes" to match the PIL HUD overlay graphics.

---

### AI Horde: Stable Diffusion Models
AI Horde workers run models like Dreamshaper, Deliberate, or SDXL. These respond best to dense, high-impact style tags and strict negative prompts to filter out common Stable Diffusion artifacts.

**Proposed Prompt Template**:
```python
prompt = (
    f"dark high-contrast techno-gaming background of {clean_keywords}, cyberpunk hacker style, "
    "glowing neon cyan and hot red circuit lines, digital grid overlay, futuristic HUD reticle "
    "in upper half, clean dark bottom region, deep shadows, cinematic lighting, highly detailed "
    "### text, words, letters, logo, signature, watermark, bright background, white background, "
    "daylight, out of focus, crowded bottom, blurry"
)
```

**Why it works**:
- **Negative Prompt Injection**: The `###` separator is recognized by the AI Horde API. The negative prompt explicitly blocks `text, words, letters, logo, signature, watermark` (preventing text hallucination) and `bright background, white background, daylight, crowded bottom` (enforcing a dark background suitable for text overlays).
- **Keyword Weighting**: Emphasizes "dark high-contrast techno-gaming" at the front of the prompt to maximize attention in SD models.

---

## 3. Implementation Plan & Proposed Diff

The changes should be implemented in `smm_engine/media/image_handler.py`. Below is the proposed patch:

```diff
diff --git a/smm_engine/media/image_handler.py b/smm_engine/media/image_handler.py
--- a/smm_engine/media/image_handler.py
+++ b/smm_engine/media/image_handler.py
@@ -111,3 +111,10 @@
         clean_keywords = keywords.replace(",", " ")
-        prompt = f"cyberpunk synthwave hacker matrix code rain background {clean_keywords}, masterpiece, highly detailed, neon lights"
+        prompt = (
+            f"A dark, high-contrast techno-gaming background featuring {clean_keywords}. "
+            "The composition is vertically split: the upper half contains glowing cyberpunk neon accents, "
+            "digital HUD wireframes, and intricate circuit lines in electric cyan and vibrant red. "
+            "The lower half is a clean, dark negative space with deep black shadows and minimal gradients. "
+            "Futuristic gaming aesthetic, clean digital render, synthwave mood, dramatic atmospheric lighting, "
+            "sharp details in the upper section, 8k resolution. No text, letters, or watermark."
+        )
         
@@ -137,3 +144,9 @@
         clean_keywords = keywords.replace(",", " ")
-        prompt = f"cyberpunk matrix code rain glowing background {clean_keywords}, high resolution, hacker synthwave aesthetic"
+        prompt = (
+            f"dark high-contrast techno-gaming background of {clean_keywords}, cyberpunk hacker style, "
+            "glowing neon cyan and hot red circuit lines, digital grid overlay, futuristic HUD reticle "
+            "in upper half, clean dark bottom region, deep shadows, cinematic lighting, highly detailed "
+            "### text, words, letters, logo, signature, watermark, bright background, white background, "
+            "daylight, out of focus, crowded bottom, blurry"
+        )
         
```

### Verification Method
1. To verify the prompt content, inspect the generated image outputs in `temp_media/bg_hf.jpg` and `temp_media/bg_horde.jpg`.
2. Run `pytest tests/test_media.py` to ensure mock tests pass and generation routing is unbroken.
3. Visually verify that the resulting covers generated by `create_cover` have significantly higher contrast and that headline text at the bottom is highly legible against the newly optimized backgrounds.
