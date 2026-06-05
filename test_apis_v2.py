"""Test more APIs - round 2: content-focused APIs"""
import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def test_api(name, url, parse_fn=None, headers=None):
    try:
        hdrs = {"User-Agent": "Mozilla/5.0"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, headers=hdrs)
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        data = resp.read()
        text = data.decode("utf-8", errors="replace")
        if parse_fn:
            result = parse_fn(text)
        else:
            result = f"OK ({len(data)} bytes)"
        print(f"[OK] {name}: {result}")
        return True
    except Exception as e:
        print(f"[FAIL] {name}: {e}")
        return False

print("=" * 60)
print("ROUND 2: Content-focused APIs")
print("=" * 60)

# 1. Pexels API (free key needed, 200 req/hr)
# We'll skip key-based ones, just note them

# 2. QR Code - goqr.me (binary OK, just test connection)
test_api("GoQR.me (QR codes)",
    "https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=test&format=png",
    lambda d: f"OK, got PNG image")

# 3. Readability - Mercury Parser alternative: readable.so / Diffbot
# Actually let's test readability-lxml locally
print("\n--- News/Content extraction ---")

# 4. Hacker News - Algolia Search API (powerful, free, no key)
test_api("HN Algolia Search (AI news)",
    "https://hn.algolia.com/api/v1/search?query=artificial+intelligence&tags=story&hitsPerPage=3",
    lambda d: f"OK, {json.loads(d).get('nbHits', 0)} results, top: \"{json.loads(d)['hits'][0]['title'][:50]}...\"")

# 5. HN Algolia - search for gaming
test_api("HN Algolia Search (gaming)",
    "https://hn.algolia.com/api/v1/search?query=gaming+GPU&tags=story&hitsPerPage=3",
    lambda d: f"OK, {json.loads(d).get('nbHits', 0)} results")

# 6. HN Algolia - front page
test_api("HN Algolia (front page)",
    "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=5",
    lambda d: f"OK, top5: {[h['title'][:30] for h in json.loads(d)['hits'][:3]]}")

# 7. Dev.to API (tech articles, free, no key)
test_api("Dev.to Articles",
    "https://dev.to/api/articles?tag=ai&per_page=3",
    lambda d: f"OK, {len(json.loads(d))} articles, top: \"{json.loads(d)[0]['title'][:50]}...\"")

# 8. Dev.to - gaming tag
test_api("Dev.to (gamedev)",
    "https://dev.to/api/articles?tag=gamedev&per_page=3",
    lambda d: f"OK, {len(json.loads(d))} articles")

# 9. Product Hunt API (needs OAuth, skip)

# 10. RSS2JSON - convert RSS to JSON (free, no key, 10k req/day)
test_api("RSS2JSON (GamersNexus RSS)",
    "https://api.rss2json.com/v1/api.json?rss_url=https://gamersnexus.net/rss.xml&count=3",
    lambda d: f"OK, feed: \"{json.loads(d).get('feed',{}).get('title','N/A')}\", {len(json.loads(d).get('items',[]))} items")

# 11. Itch.io (free games, no key)
test_api("Itch.io Feed",
    "https://itch.io/feed/featured.json",
    lambda d: f"OK, content length: {len(d)} bytes")

# 12. Steam News API (free, no key)
test_api("Steam News API",
    "https://api.steampowered.com/ISteamNews/GetNewsForApp/v0002/?appid=440&count=3&maxlength=100&format=json",
    lambda d: f"OK, {len(json.loads(d).get('appnews',{}).get('newsitems',[]))} news items")

# 13. Imgflip - meme templates (free, no key to list)
test_api("Imgflip Meme Templates",
    "https://api.imgflip.com/get_memes",
    lambda d: f"OK, {len(json.loads(d).get('data',{}).get('memes',[]))} templates")

# 14. Lorem Ipsum / Lorem Markdownum (for testing)
test_api("LoremFlickr (themed images)",
    "https://loremflickr.com/json/800/600/technology,gaming",
    lambda d: f"OK, image: {json.loads(d).get('file', 'N/A')[:60]}...")

# 15. TechCrunch RSS via RSS2JSON
test_api("RSS2JSON (TechCrunch)",
    "https://api.rss2json.com/v1/api.json?rss_url=https://techcrunch.com/feed/&count=3",
    lambda d: f"OK, feed: \"{json.loads(d).get('feed',{}).get('title','N/A')}\", {len(json.loads(d).get('items',[]))} items")

# 16. The Verge RSS
test_api("RSS2JSON (The Verge)",
    "https://api.rss2json.com/v1/api.json?rss_url=https://www.theverge.com/rss/index.xml&count=3",
    lambda d: f"OK, feed: \"{json.loads(d).get('feed',{}).get('title','N/A')}\", {len(json.loads(d).get('items',[]))} items")

# 17. ArsTechnica RSS
test_api("RSS2JSON (ArsTechnica)",
    "https://api.rss2json.com/v1/api.json?rss_url=https://feeds.arstechnica.com/arstechnica/index&count=3",
    lambda d: f"OK, feed: \"{json.loads(d).get('feed',{}).get('title','N/A')}\", {len(json.loads(d).get('items',[]))} items")

# 18. is-a.dev (test trending GitHub repos for tools)
test_api("GitHub Search (AI tools this week)",
    "https://api.github.com/search/repositories?q=topic:ai+created:>2026-05-29&sort=stars&per_page=3",
    lambda d: f"OK, {json.loads(d).get('total_count',0)} repos, top: \"{json.loads(d)['items'][0]['full_name'] if json.loads(d)['items'] else 'N/A'}\"")

# 19. Random User (for avatars/testing)
test_api("RandomUser API",
    "https://randomuser.me/api/?results=1",
    lambda d: f"OK, user: {json.loads(d)['results'][0]['name']['first']} {json.loads(d)['results'][0]['name']['last']}")

# 20. URLhaus (malware URLs - for filtering)
# Skip, not relevant

# 21. Abstract API - IP geolocation (free tier)
# Needs key, skip

# 22. Cataas (Cat as a service - fun content for posts)
test_api("Cataas (cat images)",
    "https://cataas.com/cat/says/AI%20News?fontSize=50&fontColor=white&type=square",
    lambda d: f"OK, cat image ({len(d)} bytes)")

print("\n" + "=" * 60)
print("ROUND 2 COMPLETE")
