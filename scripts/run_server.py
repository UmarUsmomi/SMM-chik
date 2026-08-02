"""Start the FastAPI service with the repository root on ``sys.path``."""

import os
from pathlib import Path
import sys


repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "bot.app:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "10000")),
        log_level=os.getenv("LOG_LEVEL", "info"),
    )
