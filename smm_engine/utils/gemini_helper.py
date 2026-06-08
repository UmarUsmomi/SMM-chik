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
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "openrouter:meta-llama/llama-3.1-70b-instruct:free",
    "openrouter:meta-llama/llama-3.1-8b-instruct:free",
    "openrouter:google/gemma-2-9b-it:free",
    "openrouter:mistralai/mistral-7b-instruct:free",
    "openrouter:microsoft/phi-3-mini-128k-instruct:free"
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

async def _generate_with_openrouter(prompt: str, model_name: str, generation_config: dict = None) -> str:
    import httpx
    import json
    from smm_engine.config import OPENROUTER_API_KEY
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is not set")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com/UmarUsmomi/SMM-chik",
        "X-Title": "SMM-chik",
        "Content-Type": "application/json"
    }
    
    system_prompt = "You are a helpful assistant."
    if generation_config and generation_config.get("response_mime_type") == "application/json":
        system_prompt += " You must return valid JSON."
    
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
    }
    
    if generation_config and "temperature" in generation_config:
        payload["temperature"] = generation_config["temperature"]
        
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=45)
        if resp.status_code == 200:
            data = resp.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                raise ValueError("OpenRouter API returned invalid format: " + str(data))
        else:
            raise ValueError(f"OpenRouter API error {resp.status_code}: {resp.text}")

async def generate_content_with_retry(prompt: str, initial_model: str, generation_config: dict = None) -> str:
    """Generates content using Gemini API with exponential backoff on 429/RPM limits
    and fallback to OpenRouter free-tier models on daily quota exhaustion."""
    
    # Construct sequence of models to try, filtering out OpenRouter models if key is missing
    from smm_engine.config import OPENROUTER_API_KEY
    has_or_key = bool(OPENROUTER_API_KEY)
    
    def is_allowed(model_name):
        if model_name.startswith("openrouter:") and not has_or_key:
            return False
        return True

    models_to_try = []
    if initial_model and is_allowed(initial_model):
        models_to_try.append(initial_model)
    for model in FALLBACK_MODELS:
        if model not in models_to_try and is_allowed(model):
            models_to_try.append(model)
            
    if not has_or_key:
        # Check if we have any OpenRouter models filtered out and log warning
        has_filtered = any(m.startswith("openrouter:") for m in [initial_model] + FALLBACK_MODELS if m)
        if has_filtered:
            logger.warning("OPENROUTER_API_KEY is missing. All OpenRouter fallback models will be skipped.")
            
    last_exception = None
    
    for model_name in models_to_try:
        # We will try up to 2 times for rate limit (RPM) errors per model
        max_retries = 2
        backoff = 15.0  # Start with 15s to respect the 15 RPM quota
        
        for attempt in range(max_retries):
            try:
                if model_name.startswith("openrouter:"):
                    or_model = model_name.split(":", 1)[1]
                    logger.info(f"Attempting content generation using OpenRouter model: {or_model}")
                    response_text = await _generate_with_openrouter(prompt, or_model, generation_config)
                    logger.info(f"Successfully generated content with OpenRouter model {or_model}")
                    return response_text
                else:
                    logger.info(f"Attempting content generation using Gemini model: {model_name}")
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(
                        prompt,
                        generation_config=generation_config
                    )
                    
                    if response and response.text:
                        logger.info(f"Successfully generated content with Gemini model {model_name}")
                        return response.text
                    else:
                        raise ValueError("Gemini API returned an empty response text.")
                    
            except ResourceExhausted as e:
                err_msg = str(e)
                logger.warning(f"Resource exhausted (429) on model {model_name}, attempt {attempt+1}/{max_retries}: {err_msg}")
                
                if _is_daily_quota_error(err_msg):
                    logger.warning(f"Daily quota limit exceeded for model {model_name}. Switching to next model immediately.")
                    last_exception = e
                    break # Break retry loop to try the next model
                    
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
                
                if _is_daily_quota_error(err_msg) or "429" in err_msg:
                    if _is_daily_quota_error(err_msg):
                        logger.warning(f"Daily quota limit detected via generic error on model {model_name}. Switching model.")
                        last_exception = e
                        break # Try next model
                    
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
    raise RuntimeError(f"All models failed. Last error: {last_exception}")

def parse_json_robust(text: str) -> dict:
    """Robustly parses a JSON string, stripping markdown code block wrappers if present."""
    import json
    import re
    if not text:
        return {}
    cleaned = text.strip()
    
    # Remove markdown code blocks if the model wrapped it (e.g. ```json ... ```)
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', cleaned, re.DOTALL | re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()
    else:
        # Check if there is any stray leading/trailing markdown characters or text
        # Find first '{' and last '}'
        start_idx = cleaned.find('{')
        end_idx = cleaned.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            cleaned = cleaned[start_idx:end_idx+1]
            
    return json.loads(cleaned)
