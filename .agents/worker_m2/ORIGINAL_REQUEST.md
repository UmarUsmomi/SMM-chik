## 2026-06-12T14:35:25Z
You are the worker subagent (teamwork_preview_worker) for Milestone 2 (Graphics Layout & Fonts) of the SMM bot modernization project.
Your working directory is: d:\SMM\.agents\worker_m2\
Your task is to implement the following changes in `smm_engine/media/image_handler.py`:

1. **R1: Clean up HUD graphics**
   In `_draw_tech_graphics()`, completely remove:
   - The central reticle and crosshairs (lines 455-476).
   - The coordinate grid lines, labels (`X_xxx` and `Y_yyy`), and the intersection crosses (`+` signs) (lines 478-514).
   Keep only:
   - Decorative borders and corner L-brackets (these are drawn in `create_cover` already).
   - Parallel circuit paths (lines 515-560).
   - Border tick scales (lines 562-570).
   - HUD corner labels (lines 572-584).

2. **R4: Remove watermarks**
   In `create_cover()`, remove or disable the rendering of the branded watermark `/ игры ⚡ патчи /` (lines 783-869). You can comment out or delete the block starting with `if wm_config:` entirely.

3. **R5: Russo One font & Cyberpunk card**
   - In `_setup_font()`, replace all references to `Montserrat-Bold.ttf` with `RussoOne-Regular.ttf`.
   - Update the download URL to auto-download Russo One from Google Fonts if it doesn't exist locally:
     `https://github.com/google/fonts/raw/main/ofl/russoone/RussoOne-Regular.ttf`
     Save the downloaded font as `RussoOne-Regular.ttf` in `self.temp_dir`.
   - In `create_cover()` headline rendering:
     - Remove the plain text shadow rendering.
     - Draw a semi-transparent dark backing card (HUD card) with a thin border styled after Cyberpunk 2077 around the headline text block.
       - The card should start at `card_x1 = pad_left - 30` (or `24` if vertical) and end at `card_x2 = width - pad_left + 30`.
       - It should start at `card_y1 = y_start_initial - 20` and end at `card_y2 = y_start_final + 20` (where `y_start_initial` is `height - total_text_height - 80` and `y_start_final` is `height - 80` or similar).
       - Fill the card with a semi-transparent dark color (e.g. `(brand_dark[0], brand_dark[1], brand_dark[2], 200)`).
       - Draw a thin border of accent color (e.g. `(brand_accent[0], brand_accent[1], brand_accent[2], 120)`). Consider cutting the top-left corner by 15px for a Cyberpunk polygon look! E.g. using `draw.polygon([(card_x1 + 15, card_y1), (card_x2, card_y1), (card_x2, card_y2), (card_x1, card_y2), (card_x1, card_y1 + 15)])`.
     - Add a vertical neon indicator bar of the accent color to the left of the text block inside or on the border of the card:
       - Glow line: width 6, color `(brand_accent[0], brand_accent[1], brand_accent[2], 60)`.
       - Core line: width 2, color `(brand_accent[0], brand_accent[1], brand_accent[2], 255)`.
       - Located at `indicator_x = card_x1 + 8` (or similar), from `card_y1 + 20` to `card_y2 - 10`.
     - Render the headline text lines centered or left-aligned on the card using the Russo One font.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

After editing the code, run unit tests to verify your implementation.
Write a report of your changes and test results to `d:\SMM\.agents\worker_m2\handoff.md` and send a message back to the orchestrator (conversation ID: 729f88fb-0e2a-4076-886d-f90f3c5b847e).
