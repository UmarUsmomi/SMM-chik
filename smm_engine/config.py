import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    GEMINI_API_KEY = GEMINI_API_KEY.strip().strip("'\"")

SCORER_MODEL = os.getenv("SCORER_MODEL", "gemini-3.1-flash-lite")
ADAPTER_MODEL = os.getenv("ADAPTER_MODEL", "gemini-3.1-flash-lite")
HUMANIZER_MODEL = os.getenv("HUMANIZER_MODEL", "gemini-3.1-flash-lite")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if TELEGRAM_BOT_TOKEN:
    TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN.strip().strip("'\"")

TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
if TELEGRAM_CHANNEL_ID:
    TELEGRAM_CHANNEL_ID = TELEGRAM_CHANNEL_ID.strip().strip("'\"")

# Database (Supabase or local SQLite)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "smm_database.db"))

# Imgflip for memes
IMGFLIP_USERNAME = os.getenv("IMGFLIP_USERNAME")
IMGFLIP_PASSWORD = os.getenv("IMGFLIP_PASSWORD")

# Thresholds
AUTO_PUBLISH_THRESHOLD = int(os.getenv("AUTO_PUBLISH_THRESHOLD", "85"))
QUEUE_THRESHOLD = int(os.getenv("QUEUE_THRESHOLD", "70"))

# Load YAML configs
def load_yaml_config(file_path: Path):
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

SOURCES_CONFIG = load_yaml_config(BASE_DIR / "config" / "sources.yaml")
STYLE_GUIDE = load_yaml_config(BASE_DIR / "config" / "style_guide.yaml")

def check_required_env():
    """Validates essential configuration parameters"""
    missing = []
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHANNEL_ID:
        missing.append("TELEGRAM_CHANNEL_ID")
    return missing
