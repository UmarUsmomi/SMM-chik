import re
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent

# Popular/legitimate target packages that are often typosquatted
POPULAR_PACKAGES = [
    "requests", "numpy", "pillow", "fastapi", "uvicorn", "pytest", 
    "jinja2", "pyyaml", "httpx", "feedparser", "psycopg2-binary", 
    "python-dotenv", "google-generativeai", "pytest-asyncio"
]

def levenshtein_distance(s1: str, s2: str) -> int:
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
    return re.sub(r"[-_.]+", "-", name).lower()

def test_no_dependency_typosquatting():
    """Verify that no packages in requirements.txt are potential typosquats of popular libraries."""
    req_file = ROOT / "requirements.txt"
    assert req_file.exists(), "requirements.txt does not exist!"
    
    packages = []
    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(r"^([a-zA-Z0-9\-_.]+)", line)
            if match:
                packages.append(match.group(1))
                
    assert len(packages) > 0, "No packages found in requirements.txt"
    
    suspicious = []
    for pkg in packages:
        norm_name = normalize_name(pkg)
        is_legit_match = False
        
        # Check if it matches exactly one of the popular/known packages
        for popular in POPULAR_PACKAGES:
            norm_popular = normalize_name(popular)
            if norm_name == norm_popular:
                is_legit_match = True
                break
                
        if is_legit_match:
            continue
            
        # Check edit distance to prevent close misspellings (typosquatting)
        for popular in POPULAR_PACKAGES:
            norm_popular = normalize_name(popular)
            dist = levenshtein_distance(norm_name, norm_popular)
            if dist <= 2:
                suspicious.append(f"Package '{pkg}' is close to popular package '{popular}' (Levenshtein distance: {dist})")
                
    assert not suspicious, f"Potential typosquatting packages detected: {suspicious}"
