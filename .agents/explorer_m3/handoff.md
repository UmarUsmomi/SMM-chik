# Handoff Report — Explorer 3: Demo Cover Generation Script Design

**Summary**: The `ImageGenerator` class has a zero-argument constructor and a synchronous `create_cover(title, bg_path=None, vertical=False) -> Path` method. Covers can be generated fully offline using procedural backgrounds (no API calls needed). Themes are loaded at init time from `BRANDING_THEME` env var but the `self.theme` dict can be monkey-patched at runtime for multi-theme iteration. Three themes exist: `default`, `cyberpunk`, `dracula`.

---

## 1. Observation

### 1.1 ImageGenerator Constructor (`image_handler.py:12-19`)

```python
class ImageGenerator:
    def __init__(self):
        self.temp_dir = BASE_DIR / "temp_media"
        self.temp_dir.mkdir(exist_ok=True)
        self.font_path = self._setup_font()
        self.theme = self._load_theme()
```

- **Takes zero arguments**. No dependencies to inject.
- Creates `d:/SMM/temp_media/` directory automatically.
- Loads bundled font from `d:/SMM/fonts/Montserrat-Bold.ttf` (confirmed present via `find_by_name`).
- Loads theme from `BRANDING_THEME` env var (default: `"default"`) via `_load_theme()`.

### 1.2 `create_cover()` API (`image_handler.py:516-782`)

```python
def create_cover(self, title: str, bg_path: Path = None, vertical: bool = False) -> Path:
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `title` | `str` | (required) | Headline text rendered on the cover |
| `bg_path` | `Path` | `None` | Path to background image; if `None`, generates procedural gradient |
| `vertical` | `bool` | `False` | If `True`, produces 720×1280 (9:16); if `False`, 1080×1080 (1:1) |
| **Returns** | `Path` or `None` | — | Path to generated JPEG, or `None` on error |

**Output path**: Always writes to `self.temp_dir / "final_cover.jpg"` (square) or `self.temp_dir / "final_cover_v.jpg"` (vertical). **This means consecutive calls overwrite the file** — the caller must rename/copy before the next call.

**Key pipeline inside `create_cover()`**:
1. Load & crop background OR generate procedural gradient (`_generate_procedural_background`)
2. Apply glitch effect (`_apply_glitch_effect`)
3. Dark gradient overlay for text readability
4. HUD decorative elements (inner border, L-brackets, tech graphics)
5. Headline text rendering with word-wrap and shadow
6. Branded watermark in bottom-right
7. Save as JPEG quality=95

**Title sanitization** (lines 647-659): strips HTML tags, unicode chars ≥ U+2000, trims to 65 chars with smart truncation at punctuation.

**Fully synchronous** — no `async` keyword. Can be called directly in a regular `def main()`.

### 1.3 Theme Loading (`image_handler.py:69-113`)

```python
def _load_theme(self) -> dict:
    from smm_engine.config import BRANDING_THEME
    theme_path = BASE_DIR / "themes" / f"{BRANDING_THEME}.yaml"
```

- Reads `BRANDING_THEME` from `smm_engine.config`, which reads from env var `BRANDING_THEME` (default `"default"`).
- Falls back to a hardcoded dict if the YAML file is missing.
- **`self.theme` is a plain dict** — can be reassigned at runtime:
  ```python
  gen = ImageGenerator()
  gen.theme = yaml.safe_load(open("themes/cyberpunk.yaml"))
  ```

### 1.4 Available Themes

| Theme file | Name | Accent color |
|------------|------|-------------|
| `themes/default.yaml` | "Default Dark & Red Tech/Gaming Theme" | Red `[217, 4, 41]` |
| `themes/cyberpunk.yaml` | "Cyberpunk neon theme" | Neon Yellow `[252, 238, 10]` |
| `themes/dracula.yaml` | "Dracula purple/pink theme" | Pink `[255, 121, 198]` |

All share the same structure: `colors`, `layout`, `watermark` sections.

### 1.5 Existing Scratch Script Pattern (`scratch/test_new_design.py`)

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smm_engine.media.image_handler import ImageGenerator
from PIL import Image

def main():
    gen = ImageGenerator()
    
    # Generate cover
    result = gen.create_cover(title="...", bg_path=None, vertical=False)
    
    # Rename output to preserve it
    dest = result.parent / "descriptive_name.jpg"
    if result.exists():
        if dest.exists():
            dest.unlink()
        result.rename(dest)

if __name__ == "__main__":
    main()
```

Key patterns:
- Adds project root to `sys.path` via `sys.path.insert(0, ...)`
- Uses synchronous `main()` (not async)
- Creates a dummy background image with PIL for testing photo-overlay mode
- Renames output files to prevent overwriting

### 1.6 Background Handling — Offline Mode

**YES, covers can be generated fully offline.** When `bg_path=None`, `create_cover()` calls `_generate_procedural_background()` (line 557) which creates a gradient image entirely in-memory using PIL — no network calls. The font is bundled locally at `d:/SMM/fonts/Montserrat-Bold.ttf`.

The only network-dependent methods are:
- `fetch_background()` — downloads from LoremFlickr/Unsplash
- `generate_hf_background()` — calls Hugging Face API
- `generate_horde_background()` — calls AI Horde API
- `generate_ai_background()` — routes between HF/Horde

None of these are called by `create_cover()` — they're separate methods the pipeline calls before `create_cover()`.

---

## 2. Logic Chain

1. **Observation**: `ImageGenerator.__init__()` takes zero args → can be instantiated with just `gen = ImageGenerator()`.
2. **Observation**: `create_cover()` is synchronous and returns a `Path` → no asyncio needed.
3. **Observation**: When `bg_path=None`, procedural gradient is used → no network dependency.
4. **Observation**: Output always goes to `temp_media/final_cover.jpg` or `final_cover_v.jpg` → must copy/rename immediately after each call.
5. **Observation**: `self.theme` is a plain dict → can be replaced at runtime to test multiple themes without re-instantiating.
6. **Observation**: `test_new_design.py` demonstrates the exact pattern for a standalone scratch script.
7. **Inference**: A demo script can iterate over themes × formats × titles, assigning `gen.theme` per iteration and renaming output files.

---

## 3. Caveats

- **Theme monkey-patching**: Replacing `self.theme` directly works because `create_cover()` reads `self.theme.get(...)` each call. However, this bypasses the logged "Loaded branding theme" message. Not a functional concern.
- **Font availability**: If `fonts/Montserrat-Bold.ttf` is missing, `_setup_font()` will attempt an HTTP download. The font is confirmed present.
- **Output overwrite race**: If the script crashes between `create_cover()` and the rename, the file is lost. The demo script should use `shutil.copy2` rather than rename for safety.
- **Dummy backgrounds**: `test_new_design.py` creates a simple colored rectangle as dummy bg. For a more realistic demo, we could create more interesting procedural dummy backgrounds with gradients/shapes, but the procedural mode (bg_path=None) already produces a polished gradient result.

---

## 4. Conclusion — Proposed Script Design

### Script: `scratch/generate_demo_covers.py`

```python
"""
Generate demo covers for visual QA across all themes, formats, and title lengths.
Fully offline — no API calls needed.

Usage:
    python scratch/generate_demo_covers.py
    
Output:
    scratch/demo_output/<theme>/<format>_<title_slug>.jpg
"""

import sys
import shutil
import yaml
from pathlib import Path
from PIL import Image, ImageDraw

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from smm_engine.media.image_handler import ImageGenerator

# --- Configuration ---

OUTPUT_DIR = ROOT / "scratch" / "demo_output"

THEMES = ["default", "cyberpunk", "dracula"]

TITLES = {
    "short": "Обновление CS2",
    "medium": "Новая видеокарта RTX 5090 бьет рекорды в играх",
    "long": "Microsoft анонсировала Windows 12 с глубокой интеграцией AI — что изменится для геймеров и разработчиков",
    "emoji": "🎮 Топ-5 игр лета 2026: что стоит попробовать",
    "english": "NVIDIA GeForce RTX 5090 Review: The New King of 4K Gaming",
}

FORMATS = [
    {"name": "square", "vertical": False},   # 1080x1080
    {"name": "vertical", "vertical": True},   # 720x1280
]


def create_dummy_background(path: Path):
    """Create a simple dummy background image for photo-overlay testing."""
    img = Image.new("RGB", (1280, 720), color=(30, 35, 50))
    draw = ImageDraw.Draw(img)
    # Add some visual elements
    for i in range(0, 1280, 80):
        draw.line([(i, 0), (i, 720)], fill=(50, 55, 70), width=1)
    for j in range(0, 720, 80):
        draw.line([(0, j), (1280, j)], fill=(50, 55, 70), width=1)
    draw.ellipse([400, 200, 880, 520], fill=(60, 80, 120))
    img.save(path)


def load_theme(theme_name: str) -> dict:
    """Load a theme YAML file by name."""
    theme_path = ROOT / "themes" / f"{theme_name}.yaml"
    with open(theme_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def slugify(text: str, max_len: int = 30) -> str:
    """Create a filesystem-safe slug from text."""
    import re
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[\s_]+', '_', slug).strip('_')
    return slug[:max_len]


def main():
    gen = ImageGenerator()
    
    # Also create a dummy bg for photo-overlay tests
    dummy_bg = ROOT / "scratch" / "demo_output" / "_dummy_bg.jpg"
    dummy_bg.parent.mkdir(parents=True, exist_ok=True)
    create_dummy_background(dummy_bg)
    
    total = 0
    errors = []
    
    for theme_name in THEMES:
        # Load and apply theme
        try:
            gen.theme = load_theme(theme_name)
        except Exception as e:
            print(f"ERROR: Failed to load theme '{theme_name}': {e}")
            errors.append(f"Theme load: {theme_name}")
            continue
        
        theme_dir = OUTPUT_DIR / theme_name
        theme_dir.mkdir(parents=True, exist_ok=True)
        
        for fmt in FORMATS:
            for title_key, title_text in TITLES.items():
                # --- Procedural background ---
                filename = f"{fmt['name']}_proc_{title_key}.jpg"
                print(f"  [{theme_name}] {filename}...")
                
                try:
                    result = gen.create_cover(
                        title=title_text,
                        bg_path=None,
                        vertical=fmt["vertical"]
                    )
                    if result and result.exists():
                        dest = theme_dir / filename
                        shutil.copy2(result, dest)
                        total += 1
                    else:
                        errors.append(f"No output: {filename}")
                except Exception as e:
                    print(f"    ERROR: {e}")
                    errors.append(f"{theme_name}/{filename}: {e}")
                
                # --- Photo background (only for one title to save time) ---
                if title_key == "medium":
                    photo_filename = f"{fmt['name']}_photo_{title_key}.jpg"
                    print(f"  [{theme_name}] {photo_filename}...")
                    try:
                        result = gen.create_cover(
                            title=title_text,
                            bg_path=dummy_bg,
                            vertical=fmt["vertical"]
                        )
                        if result and result.exists():
                            dest = theme_dir / photo_filename
                            shutil.copy2(result, dest)
                            total += 1
                        else:
                            errors.append(f"No output: {photo_filename}")
                    except Exception as e:
                        print(f"    ERROR: {e}")
                        errors.append(f"{theme_name}/{photo_filename}: {e}")
    
    # --- Summary ---
    print(f"\n{'='*50}")
    print(f"Generated {total} covers in: {OUTPUT_DIR}")
    if errors:
        print(f"\n{len(errors)} errors:")
        for e in errors:
            print(f"  - {e}")
    else:
        print("No errors!")


if __name__ == "__main__":
    main()
```

### Design Rationale

| Decision | Rationale |
|----------|-----------|
| `shutil.copy2` instead of `rename` | Safer; avoids data loss if script crashes mid-iteration |
| Monkey-patch `gen.theme` | Avoids needing to re-instantiate `ImageGenerator` per theme; `create_cover()` reads `self.theme` each call |
| Separate `load_theme()` helper | Decouples from env var mechanism; loads any theme by name |
| Procedural + photo backgrounds | Tests both code paths in `create_cover()` |
| 5 title variations | Covers short (2 words), medium (~10 words), long (truncation trigger >65 chars), emoji, and English |
| Both formats per title | Tests square (1080×1080) and vertical (720×1280) |
| Output organized by `theme/format_bgtype_titlelength.jpg` | Easy visual comparison during QA |
| Error collection, not early exit | Generates as many covers as possible even if some fail |

### Expected Output Structure
```
scratch/demo_output/
├── _dummy_bg.jpg
├── default/
│   ├── square_proc_short.jpg
│   ├── square_proc_medium.jpg
│   ├── square_proc_long.jpg
│   ├── square_proc_emoji.jpg
│   ├── square_proc_english.jpg
│   ├── square_photo_medium.jpg
│   ├── vertical_proc_short.jpg
│   ├── vertical_proc_medium.jpg
│   ├── vertical_proc_long.jpg
│   ├── vertical_proc_emoji.jpg
│   ├── vertical_proc_english.jpg
│   └── vertical_photo_medium.jpg
├── cyberpunk/
│   └── (same 12 files)
└── dracula/
    └── (same 12 files)
```

**Total: 36 cover images** (3 themes × 2 formats × 5 titles + 3 themes × 2 formats × 1 photo)

---

## 5. Verification Method

1. **Run the existing test script** to confirm the API works:
   ```
   cd d:\SMM && python scratch/test_new_design.py
   ```
   Expected: 4 JPEGs in `temp_media/` directory.

2. **Run the proposed demo script** (once implemented):
   ```
   cd d:\SMM && python scratch/generate_demo_covers.py
   ```
   Expected: 36 JPEGs organized in `scratch/demo_output/`.

3. **Visual QA**: Open the output directory and inspect covers for:
   - Text readability and proper word-wrapping
   - Theme color differences (red accent vs yellow vs pink)
   - Correct dimensions (1080×1080 square, 720×1280 vertical)
   - Title truncation on "long" variant
   - Emoji rendering on "emoji" variant
   - Watermark visibility in bottom-right corner

4. **Invalidation condition**: If `ImageGenerator.__init__()` signature changes to require arguments, the script design must be updated.
