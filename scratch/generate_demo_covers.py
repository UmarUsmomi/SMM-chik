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
    print("Initializing ImageGenerator...")
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
            print(f"Loaded theme: {theme_name}")
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
                print(f"  [{theme_name}] Generating {filename}...")
                
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
                    print(f"  [{theme_name}] Generating {photo_filename}...")
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
