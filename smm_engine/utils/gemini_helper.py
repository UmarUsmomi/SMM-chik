import asyncio
import logging
import google.generativeai as genai
from google.api_core.exceptions import GoogleAPICallError, ResourceExhausted

from smm_engine.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

# Configure gemini globally
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# List of models to try in case of quota exhaustion
FALLBACK_MODELS = [
    "gemini-3.1-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b"
]

def _is_daily_quota_error(error_msg: str) -> bool:
    """Detects if the error is a daily quota exhaustion, which won't resolve with a simple sleep"""
    msg_lower = error_msg.lower()
    return (
        "quota exceeded" in msg_lower or
        "limit: 20" in msg_lower or
        "generaterequestsperday" in msg_lower or
        "daily" in msg_lower or
        "free_tier_requests" in msg_lower
    )

async def generate_content_with_retry(prompt: str, initial_model: str, generation_config: dict = None) -> str:
    """Generates content using Gemini API with exponential backoff on 429/RPM limits
    and fallback to other free-tier models on daily quota exhaustion."""
    
    # Construct sequence of models to try
    models_to_try = []
    if initial_model:
        models_to_try.append(initial_model)
    for model in FALLBACK_MODELS:
        if model not in models_to_try:
            models_to_try.append(model)
            
    last_exception = None
    
    for model_name in models_to_try:
        logger.info(f"Attempting content generation using model: {model_name}")
        model = genai.GenerativeModel(model_name)
        
        # We will try up to 3 times for rate limit (RPM) errors per model
        max_retries = 3
        backoff = 2.0
        
        for attempt in range(max_retries):
            try:
                # generate_content is blocking, run in executor if necessary or call directly
                # To keep it simple and clean, calling directly
                response = model.generate_content(
                    prompt,
                    generation_config=generation_config
                )
                
                # Verify we got a valid response
                if response and response.text:
                    logger.info(f"Successfully generated content with model {model_name}")
                    return response.text
                else:
                    raise ValueError("Gemini API returned an empty response text.")
                    
            except ResourceExhausted as e:
                err_msg = str(e)
                logger.warning(f"Resource exhausted (429) on model {model_name}, attempt {attempt+1}/{max_retries}: {err_msg}")
                
                # Check if it's a daily limit error (e.g. 20 request limit for 3.5 flash)
                if _is_daily_quota_error(err_msg):
                    logger.warning(f"Daily quota limit exceeded for model {model_name}. Switching to next model immediately.")
                    last_exception = e
                    break # Break retry loop to try the next model
                    
                # If it's a standard RPM rate limit, sleep and retry
                if attempt < max_retries - 1:
                    sleep_time = backoff ** (attempt + 1)
                    logger.info(f"Sleeping for {sleep_time} seconds before retrying...")
                    await asyncio.sleep(sleep_time)
                else:
                    last_exception = e
                    logger.warning(f"Max retries reached for model {model_name} on rate limit.")
                    
            except Exception as e:
                err_msg = str(e)
                logger.error(f"Error calling model {model_name}: {err_msg}")
                
                # If it is a daily quota exceeded error thrown as a generic exception
                if _is_daily_quota_error(err_msg) or "429" in err_msg:
                    if _is_daily_quota_error(err_msg):
                        logger.warning(f"Daily quota limit detected via generic error on model {model_name}. Switching model.")
                        last_exception = e
                        break # Try next model
                    
                    # Otherwise RPM retry
                    if attempt < max_retries - 1:
                        sleep_time = backoff ** (attempt + 1)
                        logger.info(f"Sleeping for {sleep_time} seconds before retrying...")
                        await asyncio.sleep(sleep_time)
                    else:
                        last_exception = e
                else:
                    # Non-retryable error, try next model immediately
                    last_exception = e
                    break
                    
    # If all models failed
    raise RuntimeError(f"All Gemini models failed. Last error: {last_exception}")
