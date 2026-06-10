import re
import sys
import httpx
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Popular/legitimate target packages that are often typosquatted
POPULAR_PACKAGES = [
    "requests", "numpy", "pillow", "fastapi", "uvicorn", "pytest", 
    "jinja2", "pyyaml", "httpx", "feedparser", "psycopg2-binary", 
    "python-dotenv", "google-generativeai", "pytest-asyncio"
]

def levenshtein_distance(s1: str, s2: str) -> int:
    """Computes the Levenshtein distance between two strings (pure Python)."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
        
    return previous_row[-1]

def normalize_name(name: str) -> str:
    """PEP 503 normalization for PyPI package names."""
    return re.sub(r"[-_.]+", "-", name).lower()

def parse_requirements():
    """Parses requirements.txt and returns list of package names."""
    req_file = ROOT / "requirements.txt"
    if not req_file.exists():
        print("ERROR: requirements.txt not found!")
        return []
    
    packages = []
    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Extract package name (before specifiers like >=, ==)
            match = re.match(r"^([a-zA-Z0-9\-_.]+)", line)
            if match:
                packages.append(match.group(1))
    return packages

async def audit_package(pkg_name: str):
    """Audits a package against typosquatting and queries PyPI metadata."""
    norm_name = normalize_name(pkg_name)
    
    print(f"\nAuditing package: {pkg_name} (normalized: {norm_name})")
    
    # 1. Similarity check
    is_legit_match = False
    suspicious_matches = []
    
    for popular in POPULAR_PACKAGES:
        norm_popular = normalize_name(popular)
        if norm_name == norm_popular:
            is_legit_match = True
            break
        
        dist = levenshtein_distance(norm_name, norm_popular)
        if dist <= 2:
            suspicious_matches.append((popular, dist))
            
    if is_legit_match:
        print(f"  [OK] Legitimate match: matches popular package '{pkg_name}'")
    elif suspicious_matches:
        for popular, dist in suspicious_matches:
            print(f"  [WARN] WARNING: Name is close to popular package '{popular}' (Levenshtein distance: {dist})")
    else:
        print("  [INFO] Name matches no known close typosquats.")

    # 2. Query PyPI metadata
    url = f"https://pypi.org/pypi/{pkg_name}/json"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                info = data.get("info", {})
                releases = data.get("releases", {})
                
                author = info.get("author", "Unknown")
                latest_version = info.get("version", "Unknown")
                version_count = len(releases)
                home_page = info.get("home_page") or info.get("project_urls", {}).get("Homepage", "None")
                
                print(f"  PyPI Info:")
                print(f"    - Author: {author}")
                print(f"    - Latest Version: {latest_version}")
                print(f"    - Version Count: {version_count}")
                print(f"    - Homepage: {home_page}")
                
                # Check for low release count
                if version_count <= 2:
                    print("    - [WARN] Note: Very low release count (<= 2 releases).")
            elif resp.status_code == 404:
                print("  [ERROR] ERROR: Package not found on PyPI! Could be a private dependency or local pkg.")
            else:
                print(f"  [WARN] Warning: PyPI returned status code {resp.status_code}")
    except Exception as e:
        print(f"  [WARN] Warning: Failed to query PyPI API: {e}")

async def main():
    print("="*60)
    print("SMM Automator Dependency Security Auditor")
    print("="*60)
    
    packages = parse_requirements()
    if not packages:
        return
        
    print(f"Found {len(packages)} packages to audit in requirements.txt.")
    
    for pkg in packages:
        await audit_package(pkg)
        
    print("\n" + "="*60)
    print("Audit Complete!")
    print("="*60)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
