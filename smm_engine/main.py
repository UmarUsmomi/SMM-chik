import asyncio
import sys
import logging
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

async def main():
    logger.info("Initializing SMM Automator Engine...")
    
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
