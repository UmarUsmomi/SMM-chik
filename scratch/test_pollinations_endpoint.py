import httpx
import urllib.parse

prompt = "futuristic cyber tech style vector art representation of circuit board, high resolution, neon colors, synthwave gaming aesthetic"
encoded = urllib.parse.quote(prompt)

urls = [
    f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1080&nologo=true",
    f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1080",
    f"https://image.pollinations.ai/prompt/{encoded}?nologo=true",
    f"https://image.pollinations.ai/prompt/{encoded}",
]

async def test():
    async with httpx.AsyncClient() as client:
        for url in urls:
            try:
                resp = await client.get(url, timeout=10)
                print(f"URL: {url[:80]}...")
                print(f"Status: {resp.status_code}")
                if resp.status_code == 200:
                    print(f"Success! Content length: {len(resp.content)} bytes")
                else:
                    print(f"Response: {resp.text[:200]}")
            except Exception as e:
                print(f"Error: {e}")
            print("-" * 50)

import asyncio
asyncio.run(test())
