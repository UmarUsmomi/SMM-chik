"""Test free public APIs for SMM project"""
import urllib.request
import json
import ssl

# Bypass SSL for testing
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def test_api(name, url, parse_fn=None):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        data = resp.read().decode("utf-8")
        if parse_fn:
            result = parse_fn(data)
        else:
            result = f"OK ({len(data)} bytes)"
        print(f"✅ {name}: {result}")
        return True
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False

# 1. HackerNews API (no key)
test_api("HackerNews API", 
    "https://hacker-news.firebaseio.com/v0/topstories.json",
    lambda d: f"OK, {len(json.loads(d))} top stories")

# 2. Picsum (random images, no key)
test_api("Picsum Photos",
    "https://picsum.photos/v2/list?page=1&limit=5",
    lambda d: f"OK, {len(json.loads(d))} photos, URL: {json.loads(d)[0]['download_url'][:60]}...")

# 3. Unsplash Source (no key, direct image)
test_api("Unsplash Source",
    "https://source.unsplash.com/random/800x600/?technology",
    lambda d: f"OK, got image ({len(d)} bytes)")

# 4. Pollinations AI (free AI images, no key)
test_api("Pollinations AI (image gen)",
    "https://image.pollinations.ai/prompt/futuristic%20gaming%20setup%20neon?width=800&height=600&nologo=true",
    lambda d: f"OK, generated image ({len(d)} bytes)")

# 5. QR Code API (no key)
test_api("QR Code Generator",
    "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https://t.me/testchannel",
    lambda d: f"OK, QR code ({len(d)} bytes)")

# 6. Quotable API (random quotes, no key)
test_api("Quotable API (quotes)",
    "https://api.quotable.io/random",
    lambda d: f"OK: \"{json.loads(d).get('content', 'N/A')[:50]}...\"")

# 7. Useless Facts API (fun content, no key)
test_api("Useless Facts",
    "https://uselessfacts.jsph.pl/api/v2/facts/random?language=en",
    lambda d: f"OK: \"{json.loads(d).get('text', 'N/A')[:60]}...\"")

# 8. Screenshot API (screenshotone / microlink)
test_api("Microlink Screenshot",
    "https://api.microlink.io/?url=https://news.ycombinator.com&screenshot=true",
    lambda d: f"OK, screenshot URL: {json.loads(d).get('data',{}).get('screenshot',{}).get('url','N/A')[:60]}...")

# 9. URL Shortener (cleanuri, no key)
try:
    req_data = json.dumps({"url": "https://news.ycombinator.com/item?id=12345"}).encode()
    req = urllib.request.Request("https://cleanuri.com/api/v1/shorten", 
        data=req_data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=10, context=ctx)
    data = json.loads(resp.read().decode())
    print(f"✅ CleanURI Shortener: OK, {data.get('result_url', 'N/A')}")
except Exception as e:
    print(f"❌ CleanURI Shortener: {e}")

# 10. Reddit API (no key, .json suffix)
test_api("Reddit /r/technology",
    "https://www.reddit.com/r/technology/hot.json?limit=3",
    lambda d: f"OK, {len(json.loads(d).get('data',{}).get('children',[]))} posts")

# 11. Wikipedia random article
test_api("Wikipedia Random",
    "https://en.wikipedia.org/api/rest_v1/page/random/summary",
    lambda d: f"OK: \"{json.loads(d).get('title', 'N/A')}\"")

# 12. DuckDuckGo Instant Answers (no key)
test_api("DuckDuckGo IA",
    "https://api.duckduckgo.com/?q=artificial+intelligence&format=json&no_html=1",
    lambda d: f"OK, abstract: \"{json.loads(d).get('AbstractText', 'N/A')[:60]}...\"")

# 13. GitHub Trending (scrape via API)
test_api("GitHub Trending",
    "https://api.github.com/search/repositories?q=created:>2026-06-01+stars:>100&sort=stars&per_page=3",
    lambda d: f"OK, {json.loads(d).get('total_count', 0)} trending repos")

# 14. Pexels (needs free key, check if open)
test_api("Lorem Picsum specific",
    "https://picsum.photos/id/1/info",
    lambda d: f"OK: {json.loads(d).get('author', 'N/A')}, {json.loads(d).get('width', 'N/A')}x{json.loads(d).get('height', 'N/A')}")

# 15. IP Geolocation (free, no key)
test_api("IP-API Geolocation",
    "http://ip-api.com/json/",
    lambda d: f"OK: {json.loads(d).get('country', 'N/A')}, {json.loads(d).get('city', 'N/A')}")

# 16. Open Meteo Weather (free, no key)
test_api("Open-Meteo Weather",
    "https://api.open-meteo.com/v1/forecast?latitude=55.75&longitude=37.62&current_weather=true",
    lambda d: f"OK: Moscow {json.loads(d).get('current_weather',{}).get('temperature', 'N/A')}°C")

# 17. Catfact (fun content)
test_api("Cat Facts",
    "https://catfact.ninja/fact",
    lambda d: f"OK: \"{json.loads(d).get('fact', 'N/A')[:60]}...\"")

# 18. JokeAPI (fun content for engagement)
test_api("JokeAPI",
    "https://v2.jokeapi.dev/joke/Programming?type=single",
    lambda d: f"OK: \"{json.loads(d).get('joke', 'N/A')[:60]}...\"")

print("\n" + "="*60)
print("TESTING COMPLETE")
