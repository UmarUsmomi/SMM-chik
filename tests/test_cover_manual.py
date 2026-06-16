#!/usr/bin/env python3
"""Test script to verify create_cover works with Cyrillic text and various backgrounds."""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smm_engine.media.image_handler import ImageGenerator

async def test_covers():
    img_gen = ImageGenerator()
    test_dir = Path(__file__).resolve().parent.parent / "temp_media"
    test_dir.mkdir(exist_ok=True)

    test_cases = [
        # (title, vertical, description)
        ("РЯДУ НПЗ РАЗРЕШИЛИ ВЫПУСК БЕНЗИНА НИЗКОГО КЛАССА", False, "square_cover_test1"),
        ("Как это работает: новый ИИ от OpenAI меняет правила игры", False, "square_cover_test2"),
        ("Steam анонсировал летнюю распродажу 2025! Скидки до 90% на топовые игры", False, "square_cover_test3"),
        ("Консоли нового поколения — что скрывает Sony", True, "vertical_cover_test1"),
    ]

    for title, vertical, desc in test_cases:
        print(f"\n[TEST] Generating {desc}: {title[:50]}...")
        try:
            # Use procedural background (no AI needed for this test)
            cover_path = img_gen.create_cover(title, bg_path=None, vertical=vertical)
            if cover_path and cover_path.exists():
                # Copy to a named file for easy inspection
                dest = test_dir / f"test_{desc}.jpg"
                import shutil
                shutil.copy(cover_path, dest)
                print(f"  ✅ Saved to: {dest}")
            else:
                print(f"  ❌ Failed to generate cover")
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()

    print(f"\nAll test images saved to: {test_dir}")
    print("Check test_square_cover_test*.jpg and test_vertical_cover_test*.jpg")

if __name__ == "__main__":
    asyncio.run(test_covers())
