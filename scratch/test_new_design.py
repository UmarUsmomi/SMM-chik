import asyncio
import os
import sys
from pathlib import Path

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smm_engine.media.image_handler import ImageGenerator
from PIL import Image

def generate_dummy_image(path: Path):
    """Helper to generate a dummy background photo with some details"""
    img = Image.new("RGB", (800, 600), color=(40, 50, 70))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # draw a bright tech rectangle/circle to see how the photo overlays look
    draw.rectangle([200, 150, 600, 450], outline=(0, 255, 200), width=4)
    draw.ellipse([300, 200, 500, 400], fill=(230, 100, 50))
    img.save(path)

def main():
    print("Initializing ImageGenerator...")
    gen = ImageGenerator()
    
    # 1. Procedural Square Cover
    print("Generating procedural square cover...")
    p_square = gen.create_cover(
        title="Новая видеокарта RTX 5090 бьет рекорды производительности в CS2",
        bg_path=None,
        vertical=False
    )
    p_square_dest = p_square.parent / "procedural_square.jpg"
    if p_square.exists():
        if p_square_dest.exists():
            p_square_dest.unlink()
        p_square.rename(p_square_dest)
    print(f"Generated square procedural cover: {p_square_dest}")
    
    # 2. Procedural Vertical Cover
    print("Generating procedural vertical cover...")
    p_vertical = gen.create_cover(
        title="Как настроить Linux для максимального FPS: Гайд 2026",
        bg_path=None,
        vertical=True
    )
    p_vertical_dest = p_vertical.parent / "procedural_vertical.jpg"
    if p_vertical.exists():
        if p_vertical_dest.exists():
            p_vertical_dest.unlink()
        p_vertical.rename(p_vertical_dest)
    print(f"Generated vertical procedural cover: {p_vertical_dest}")
    
    # Create temp bg image for photo covers
    bg_dummy_path = Path("temp_media") / "dummy_bg.jpg"
    bg_dummy_path.parent.mkdir(exist_ok=True)
    generate_dummy_image(bg_dummy_path)
    
    # 3. Photo Square Cover
    print("Generating photo square cover...")
    photo_square = gen.create_cover(
        title="Microsoft анонсировала Windows 12 с глубокой интеграцией AI",
        bg_path=bg_dummy_path,
        vertical=False
    )
    photo_square_dest = photo_square.parent / "photo_square.jpg"
    if photo_square.exists():
        if photo_square_dest.exists():
            photo_square_dest.unlink()
        photo_square.rename(photo_square_dest)
    print(f"Generated photo square cover: {photo_square_dest}")
    
    # 4. Photo Vertical Cover
    print("Generating photo vertical cover...")
    photo_vertical = gen.create_cover(
        title="Секретные фишки Telegram ботов, о которых вы не знали",
        bg_path=bg_dummy_path,
        vertical=True
    )
    photo_vertical_dest = photo_vertical.parent / "photo_vertical.jpg"
    if photo_vertical.exists():
        if photo_vertical_dest.exists():
            photo_vertical_dest.unlink()
        photo_vertical.rename(photo_vertical_dest)
    print(f"Generated photo vertical cover: {photo_vertical_dest}")

if __name__ == "__main__":
    main()
