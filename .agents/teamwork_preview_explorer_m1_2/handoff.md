# Handoff Report: AI Background Prompts Analysis

This handoff report summarizes the read-only investigation of SMM background generation functions and outlines the designed optimized prompts.

---

## 1. Observation

- **Target File**: `d:\SMM\smm_engine\media\image_handler.py`
- **Lines 111-112** (`generate_hf_background`):
  ```python
  clean_keywords = keywords.replace(",", " ")
  prompt = f"cyberpunk synthwave hacker matrix code rain background {clean_keywords}, masterpiece, highly detailed, neon lights"
  ```
- **Lines 137-138** (`generate_horde_background`):
  ```python
  clean_keywords = keywords.replace(",", " ")
  prompt = f"cyberpunk matrix code rain glowing background {clean_keywords}, high resolution, hacker synthwave aesthetic"
  ```
- **Lines 291** (`_draw_tech_graphics`):
  ```python
  cx, cy = width // 2, int(height * 0.38)
  ```
  HUD reticle graphics are drawn at 38% height (upper region of the cover).
- **Lines 543-544** (`create_cover`):
  ```python
  total_text_height = len(wrapped_lines) * (font_size + 10)
  y_start = height - total_text_height - 80
  ```
  Headline text is positioned in the lower portion of the image.
- **Theme Files**: Configurations like `themes/cyberpunk.yaml` define neon cyan, yellow, and red accent colors.
- **Environment & Tests**: `requirements.txt` contains dependencies for testing (`pytest`, `pytest-asyncio`). A test run of `python -m pytest` was attempted but timed out waiting for user approval.

---

## 2. Logic Chain

1. **Title Readability vs. Background Clutter**: From the coordinates in `image_handler.py:543-544`, the title text is rendered in the bottom 40-50% of the image. If the background image contains high-contrast or bright details in that lower region, it will conflict with the text layout and reduce legibility.
2. **HUD Placement**: From `image_handler.py:291`, HUD scanning reticles and circuits are drawn in the top 50-60% of the image. The background should have details here to blend with HUD overlays, but not conflict with them.
3. **Spatial Prompt Composition**: The current prompts do not specify spatial instructions. Instructing the AI models to create detailed glowing techno components in the upper half and keep the lower half dark aligns background generation perfectly with the generator's drawing layout.
4. **FLUX.1-schnell Prompting**: FLUX is a flow-matching model that handles natural language instructions well. A descriptive paragraph outlining the layout split is optimal.
5. **AI Horde Prompting**: Stable Diffusion models hosted on AI Horde frequently render text artifacts or messy bottoms. AI Horde supports negative prompting using the `###` separator within the prompt parameter. Incorporating a comprehensive negative prompt prevents these artifacts.

---

## 3. Caveats

- **Model Variety on Horde**: Since AI Horde runs decentralized workers with different models, the visual output may vary slightly depending on which worker handles the request. We assume the standard SDXL/SD1.5 models are used.
- **Local Verification**: Direct image generation could not be tested locally because API keys (`HUGGINGFACE_API_KEY`) and live API communication were out of scope for a read-only exploration task.

---

## 4. Conclusion

The current background generation prompts can be optimized to produce high-contrast, techno-gaming backgrounds that align with the bot's overlay coordinates. Specifically:
- **FLUX.1-schnell (HF)**: Use a descriptive, split-composition natural language prompt.
- **AI Horde**: Use a tag-based prompt with negative prompt elements appended via `###`.

This will result in visually stunning, contrasty covers where text legibility is maximized, and HUD graphical overlays align with the background's detail distribution.

---

## 5. Verification Method

To verify the proposed prompts:
1. Review the proposed diff in `analysis.md`.
2. Inspect the generated backgrounds in the `temp_media/` folder once the implementer applies the changes.
3. Run the test suite:
   ```powershell
   python -m pytest tests/test_media.py
   ```
   This ensures that the prompt string construction is syntactically correct and does not crash the HTTP request payloads.
