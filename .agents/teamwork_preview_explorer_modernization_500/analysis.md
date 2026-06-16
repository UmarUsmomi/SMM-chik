# Codebase Exploration and Modernization Analysis

## Executive Summary
This analysis outlines the code locations and required changes for lowering the news length threshold for quotes to 500 characters, implementing a standalone AI background generation test script (`scratch/test_ai_generators.py`), and configuring the required environment variables in `.env.example`.

---

## 1. R1: Lowering News Length Threshold to 500 Characters

### Threshold Location in `smm_engine/content/adapter.py`
In `smm_engine/content/adapter.py`, the dynamic blockquote inclusion logic determines if a news item is "long" (which makes it eligible for random blockquote formatting) by inspecting the character count of the input content.
* **File path**: `smm_engine/content/adapter.py`
* **Line number**: 80
* **Target code**:
  ```python
  content_str = item.raw_data.get("content") or item.raw_data.get("description") or item.raw_data.get("summary") or ""
  is_long = len(content_str) > 800
  ```
* **Required change**: Change `> 800` to `> 500`.

### Selective Blockquote Tests in `tests/test_new_features.py`
The selective blockquote logic is tested in `tests/test_new_features.py`.
* **File path**: `tests/test_new_features.py`
* **Line range**: 463–522
* **Target test function**: `test_selective_blockquote`
* **Required changes**: The test comments in the test cases currently refer to `800 chars`. We should modernize these to say `500 chars` so they reflect the new threshold:
  * Line 478: `# Scenario 1: Short content (< 800 chars)` -> `# Scenario 1: Short content (< 500 chars)`
  * Line 495: `# Scenario 2: Long content (> 800 chars) with random < 0.60` -> `# Scenario 2: Long content (> 500 chars) with random < 0.60`
  * Line 513: `# Scenario 3: Long content (> 800 chars) with random >= 0.60` -> `# Scenario 3: Long content (> 500 chars) with random >= 0.60`

---

## 2. R2: AI Background Generators Integration & Testing Script

### Integration Details in `smm_engine/media/image_handler.py`
The three image generators are integrated under `ImageGenerator` class in `smm_engine/media/image_handler.py` (lines 116–260). They form a fallback chain in `generate_ai_background`: HuggingFace → Pollinations.ai → Cloudflare Workers AI → Procedural Fallback.

1. **Hugging Face (`generate_hf_background`)**:
   * **API URL**: `https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell`
   * **Authentication**: Bearer token via `HUGGINGFACE_API_KEY` (imported from `smm_engine.config`).
   * **Request Type**: `POST` containing `{"inputs": prompt}`.

2. **Pollinations.ai (`generate_pollinations_background`)**:
   * **API URL**: `https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true&seed={seed}`
   * **Authentication**: None (free, no API key needed).
   * **Request Type**: `GET` request.

3. **Cloudflare Workers AI (`generate_cloudflare_background`)**:
   * **API URL**: `https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell`
   * **Authentication**: Bearer token via `CLOUDFLARE_API_TOKEN` (imported from `smm_engine.config`).
   * **Request Type**: `POST` containing `{"prompt": prompt}`.

### Configuration / API Keys in `smm_engine/config.py`
The configuration keys are loaded from environment variables using `python-dotenv` and `os.getenv`:
* `HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")` (lines 20-22)
* `CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")` (lines 24-26)
* `CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")` (lines 28-30)

### Proposed Script: `scratch/test_ai_generators.py`
A standalone scratch script `scratch/test_ai_generators.py` is written to `d:\SMM\.agents\teamwork_preview_explorer_modernization_500\proposed_scratch_test_ai_generators.py`. It imports environment variables and runs async requests to each backend to verify integration.

---

## 3. R3: Add `HUGGINGFACE_API_KEY` to `.env.example`

* **File path**: `.env.example`
* **Target position**: The variable should be added after the Imgflip credentials section (around line 16) and before the Cloudflare section.
* **Proposed insertion**:
  ```ini
  # Hugging Face configuration (optional, used for image generation)
  HUGGINGFACE_API_KEY=
  ```

---

## 4. Test Suite Verification

* **Command run**: `pytest`
* **Result**: The test command failed to execute because `pytest` is not globally available in the current console environment, and the runner timed out waiting for manual confirmation for `python -m pytest`.
* **Observations**:
  * `requirements.txt` specifies `pytest>=8.2.2` and `pytest-asyncio>=0.23.7`.
  * `pyproject.toml` configures `pytest` under `[tool.pytest.ini_options]`.
  * The test suite in `tests/test_new_features.py` contains 16 comprehensive unit and integration tests.
