import asyncio
import os
import time
import httpx
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")

prompt = "futuristic cyber tech style vector art representation of circuit board, high resolution, neon colors, synthwave gaming aesthetic"
temp_dir = Path("temp_media")
temp_dir.mkdir(exist_ok=True)

def mask_key(val):
    if not val:
        return "MISSING"
    if len(val) <= 8:
        return "SET (too short to mask safely)"
    return f"SET (masked: {val[:4]}...{val[-4:]})"

def check_keys():
    print("=== Checking Key Availability in .env ===")
    print(f"HUGGINGFACE_API_KEY: {mask_key(HUGGINGFACE_API_KEY)}")
    print(f"CLOUDFLARE_ACCOUNT_ID: {mask_key(CLOUDFLARE_ACCOUNT_ID)}")
    print(f"CLOUDFLARE_API_TOKEN: {mask_key(CLOUDFLARE_API_TOKEN)}")
    print("-" * 50)

async def test_huggingface():
    print("=== Testing Hugging Face ===")
    if not HUGGINGFACE_API_KEY:
        print("HUGGINGFACE_API_KEY is not set. Skipping Hugging Face test.")
        return False
        
    api_url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell"
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}
    payload = {"inputs": prompt}
    img_path = temp_dir / "test_bg_hf.jpg"
    
    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(api_url, headers=headers, json=payload, timeout=45)
            elapsed = time.perf_counter() - start_time
            if resp.status_code == 200:
                img_path.write_bytes(resp.content)
                print(f"Hugging Face success! Response time: {elapsed:.2f} seconds. Saved to {img_path} ({len(resp.content)} bytes)")
                return True
            else:
                print(f"Hugging Face API failed after {elapsed:.2f}s: status={resp.status_code} response={resp.text[:200]}")
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"Hugging Face error after {elapsed:.2f}s: {e}")
    return False

async def test_pollinations():
    print("=== Testing Pollinations.ai ===")
    encoded_prompt = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1080&height=1080&nologo=true&seed=42"
    img_path = temp_dir / "test_bg_poll.jpg"
    
    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=30, follow_redirects=True)
            elapsed = time.perf_counter() - start_time
            if resp.status_code == 200 and len(resp.content) > 1000:
                img_path.write_bytes(resp.content)
                print(f"Pollinations success! Response time: {elapsed:.2f} seconds. Saved to {img_path} ({len(resp.content)} bytes)")
                return True
            else:
                print(f"Pollinations failed after {elapsed:.2f}s: status={resp.status_code}, size={len(resp.content)}")
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"Pollinations error after {elapsed:.2f}s: {e}")
    return False

async def test_cloudflare():
    print("=== Testing Cloudflare Workers AI ===")
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        print("CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN is not set. Skipping Cloudflare test.")
        return False
        
    api_url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {"prompt": prompt}
    img_path = temp_dir / "test_bg_cf.jpg"
    
    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(api_url, headers=headers, json=payload, timeout=30)
            elapsed = time.perf_counter() - start_time
            if resp.status_code == 200 and len(resp.content) > 1000:
                img_path.write_bytes(resp.content)
                print(f"Cloudflare success! Response time: {elapsed:.2f} seconds. Saved to {img_path} ({len(resp.content)} bytes)")
                return True
            else:
                print(f"Cloudflare failed after {elapsed:.2f}s: status={resp.status_code} response={resp.text[:200]}")
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        print(f"Cloudflare error after {elapsed:.2f}s: {e}")
    return False

async def main():
    check_keys()
    await test_huggingface()
    print("-" * 50)
    await test_pollinations()
    print("-" * 50)
    await test_cloudflare()

if __name__ == "__main__":
    asyncio.run(main())
