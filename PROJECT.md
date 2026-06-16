# Project: SMM Graphic Modernization

## Architecture
The SMM bot has an image generation component in `smm_engine/media/image_handler.py`. It loads theme files from `themes/*.yaml` and creates cover images (both vertical and square formats) by downloading/generating backgrounds, applying glitch effects, drawing HUD graphics, and overlaying headline text.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Investigate Codebase | Analyze `image_handler.py`, prompts, themes, and existing tests | none | IN_PROGRESS |
| 2 | Watermark Rendering | Implement branded watermark rendering in bottom-right corner of square and vertical covers with theme colors and optimal readability | 1 | PLANNED |
| 3 | AI Prompt & HUD Upgrades | Optimize AI generation prompts for FLUX.1-schnell & Horde, improve scanlines, coordinate grids, and circuit lines to look premium | 1, 2 | PLANNED |
| 4 | Verification & Testing | Write unit tests for watermark rendering, run the full pytest suite, and verify no regressions exist | 1, 2, 3 | PLANNED |

## Interface Contracts
### `ImageGenerator` API
- `create_cover(self, title: str, bg_path: Path = None, vertical: bool = False) -> Path`: Should draw the watermark on the final cover image before saving.
- Watermark drawing needs to read `self.theme.get("watermark", {})` configuration, load Montserrat-Bold font with the watermark's font size, compute watermark text segments and colors, draw a readable backing (e.g. outline/glow/semi-transparent background), and overlay it in the bottom-right corner.
- Verification command: `pytest tests/` should pass completely.
