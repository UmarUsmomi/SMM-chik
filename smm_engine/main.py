import asyncio
import logging
import os
import sys
from smm_engine.config import check_required_env
from smm_engine.pipeline import SMMPipeline

# Set up logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("smm_engine.main")

PRODUCTION_PIPELINE_REQUIRED_ENVIRONMENT = (
    "DATABASE_URL",
    "GEMINI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "TELEGRAM_ADMIN_CHAT_ID",
)


def _missing_production_configuration():
    environment = (os.getenv("ENVIRONMENT") or "").strip().lower()
    is_production = environment in {"production", "prod"} or bool(
        os.getenv("RENDER_EXTERNAL_URL")
    )
    if not is_production:
        return []
    return [
        name
        for name in PRODUCTION_PIPELINE_REQUIRED_ENVIRONMENT
        if not (os.getenv(name) or "").strip()
    ]

async def main():
    logger.info("Initializing SMM Automator Engine...")

    production_missing = _missing_production_configuration()
    if production_missing:
        logger.critical(
            "Production pipeline configuration is incomplete: %s",
            ", ".join(production_missing),
        )
        raise SystemExit(1)
    
    # Check environment variables
    missing_vars = check_required_env()
    if missing_vars:
        logger.warning(
            f"Missing environment variables: {', '.join(missing_vars)}. "
            "Engine will run in DRY-RUN mode. Actions requiring API keys will use local mock models or fallbacks."
        )
    else:
        logger.info("Environment variables validated successfully.")

    pipeline = SMMPipeline()
    try:
        summary = await pipeline.run()
        logger.info(f"Execution finished. Summary: {summary}")
    except Exception as e:
        logger.critical(f"Unhandled exception during pipeline execution: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
