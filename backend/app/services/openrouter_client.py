
import os
import asyncio
import logging
import json
import httpx

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1",
)

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")

OPENROUTER_TIMEOUT = float(
    os.getenv("OPENROUTER_TIMEOUT", "120")
)

MAX_RETRIES = 3

RETRYABLE_STATUS_CODES = {
    408,
    429,
    500,
    502,
    503,
    504,
}


# ============================================================
# OPENROUTER CLIENT
# ============================================================

class OpenRouterClient:
    """
    Reusable asynchronous OpenRouter client.

    Supports:
    - Resume analysis
    - Job description analysis
    - Interview question generation
    - Answer evaluation
    - JSON responses
    - Automatic retries
    - Provider error handling
    """

    def __init__(self):

        if not OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY is missing in .env"
            )

        if not OPENROUTER_MODEL:
            raise ValueError(
                "OPENROUTER_MODEL is missing in .env"
            )

        self.model = OPENROUTER_MODEL

        self.url = (
            f"{OPENROUTER_BASE_URL.rstrip('/')}"
            "/chat/completions"
        )

        self.headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "AI Voice Interview Platform",
        }

        self.timeout = httpx.Timeout(
            OPENROUTER_TIMEOUT,
            connect=15.0,
        )

    # ========================================================
    # RESPONSE CONTENT EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_content(message: dict) -> str:
        """
        Extract usable text from OpenRouter message content.

        Supports:
        1. Normal string content.
        2. List-based text content.
        """

        content = message.get("content")

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):

            text_parts = []

            for item in content:

                if isinstance(item, str):
                    text_parts.append(item)

                elif isinstance(item, dict):

                    if item.get("type") == "text":
                        text_value = item.get("text")

                        if isinstance(text_value, str):
                            text_parts.append(text_value)

            return "".join(text_parts).strip()

        return ""

    # ========================================================
    # PROVIDER ERROR EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_provider_error(result: dict) -> str | None:

        error = result.get("error")

        if isinstance(error, dict):
            return str(
                error.get("message")
                or error.get("code")
                or error
            )

        if error:
            return str(error)

        return None

    # ========================================================
    # GENERATE RESPONSE
    # ========================================================

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1500,
        temperature: float = 0.2,
        response_format: dict | None = None,
    ) -> str:

        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError("System prompt cannot be empty.")

        if not isinstance(user_prompt, str) or not user_prompt.strip():
            raise ValueError("User prompt cannot be empty.")

        if max_tokens < 1:
            raise ValueError("max_tokens must be greater than zero.")

        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2.")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format is not None:
            payload["response_format"] = response_format

        last_error = None

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:

            for attempt in range(1, MAX_RETRIES + 1):

                try:

                    logger.info(
                        "OpenRouter request: model=%s attempt=%s/%s",
                        self.model,
                        attempt,
                        MAX_RETRIES,
                    )

                    response = await client.post(
                        self.url,
                        headers=self.headers,
                        json=payload,
                    )

                    # ----------------------------------------
                    # HTTP ERROR HANDLING
                    # ----------------------------------------

                    if response.status_code in RETRYABLE_STATUS_CODES:

                        error_message = (
                            f"OpenRouter HTTP {response.status_code}: "
                            f"{response.text[:1000]}"
                        )

                        last_error = RuntimeError(error_message)

                        logger.warning("%s", error_message)

                        if attempt < MAX_RETRIES:

                            delay = 2 ** attempt

                            logger.info(
                                "Retrying OpenRouter in %s seconds.",
                                delay,
                            )

                            await asyncio.sleep(delay)
                            continue

                        break

                    if response.is_error:

                        raise RuntimeError(
                            f"OpenRouter HTTP error "
                            f"{response.status_code}: "
                            f"{response.text[:1000]}"
                        )

                    # ----------------------------------------
                    # RESPONSE JSON VALIDATION
                    # ----------------------------------------

                    try:
                        result = response.json()

                    except ValueError as error:

                        raise RuntimeError(
                            "OpenRouter returned invalid response JSON."
                        ) from error

                    if not isinstance(result, dict):

                        raise RuntimeError(
                            "Invalid OpenRouter response structure."
                        )

                    # ----------------------------------------
                    # PROVIDER ERROR VALIDATION
                    # ----------------------------------------

                    provider_error = self._extract_provider_error(
                        result
                    )

                    if provider_error:

                        error_message = (
                            f"OpenRouter provider error: {provider_error}"
                        )

                        last_error = RuntimeError(error_message)

                        logger.warning("%s", error_message)

                        if attempt < MAX_RETRIES:

                            await asyncio.sleep(2 ** attempt)
                            continue

                        break

                    # ----------------------------------------
                    # CHOICES VALIDATION
                    # ----------------------------------------

                    choices = result.get("choices")

                    if not isinstance(choices, list) or not choices:

                        error_message = (
                            "OpenRouter returned no choices. "
                            f"Model={result.get('model')}, "
                            f"ResponseKeys={list(result.keys())}"
                        )

                        last_error = RuntimeError(error_message)

                        logger.warning("%s", error_message)

                        if attempt < MAX_RETRIES:

                            await asyncio.sleep(2 ** attempt)
                            continue

                        break

                    choice = choices[0]

                    if not isinstance(choice, dict):

                        raise RuntimeError(
                            "Invalid choice structure from OpenRouter."
                        )

                    message = choice.get("message", {})

                    if not isinstance(message, dict):

                        raise RuntimeError(
                            "Invalid message structure from OpenRouter."
                        )

                    # ----------------------------------------
                    # CONTENT EXTRACTION
                    # ----------------------------------------

                    content = self._extract_content(message)

                    finish_reason = choice.get("finish_reason")

                    if not content:

                        error_message = (
                            "OpenRouter returned no usable content. "
                            f"Model={result.get('model')}, "
                            f"FinishReason={finish_reason}, "
                            f"MessageKeys={list(message.keys())}, "
                            f"ResponseKeys={list(result.keys())}"
                        )

                        last_error = RuntimeError(error_message)

                        logger.warning("%s", error_message)

                        if attempt < MAX_RETRIES:

                            delay = 2 ** attempt

                            logger.info(
                                "Empty response. Retrying in %s seconds.",
                                delay,
                            )

                            await asyncio.sleep(delay)
                            continue

                        break

                    # ----------------------------------------
                    # TOKEN LIMIT VALIDATION
                    # ----------------------------------------

                    if finish_reason == "length":

                        raise RuntimeError(
                            "OpenRouter response was truncated because "
                            "the token limit was reached. "
                            "Increase max_tokens."
                        )

                    # ----------------------------------------
                    # SUCCESS
                    # ----------------------------------------

                    logger.info(
                        "OpenRouter request successful. "
                        "Model=%s FinishReason=%s",
                        result.get("model", self.model),
                        finish_reason,
                    )

                    return content

                # --------------------------------------------
                # TIMEOUT HANDLING
                # --------------------------------------------

                except httpx.TimeoutException as error:

                    last_error = error

                    logger.warning(
                        "OpenRouter timeout on attempt %s/%s.",
                        attempt,
                        MAX_RETRIES,
                    )

                    if attempt < MAX_RETRIES:

                        await asyncio.sleep(2 ** attempt)
                        continue

                # --------------------------------------------
                # NETWORK ERROR HANDLING
                # --------------------------------------------

                except httpx.RequestError as error:

                    last_error = error

                    logger.warning(
                        "OpenRouter network error on attempt %s/%s: %s",
                        attempt,
                        MAX_RETRIES,
                        error,
                    )

                    if attempt < MAX_RETRIES:

                        await asyncio.sleep(2 ** attempt)
                        continue

                # --------------------------------------------
                # OTHER RUNTIME ERRORS
                # --------------------------------------------

                except RuntimeError:
                    raise

        # ====================================================
        # FINAL ERROR HANDLING
        # ====================================================

        if isinstance(last_error, httpx.TimeoutException):

            raise RuntimeError(
                f"OpenRouter request timed out after "
                f"{MAX_RETRIES} attempts. "
                f"Configured timeout: {OPENROUTER_TIMEOUT} seconds."
            ) from last_error

        if isinstance(last_error, httpx.RequestError):

            raise RuntimeError(
                f"Could not connect to OpenRouter after "
                f"{MAX_RETRIES} attempts: {last_error}"
            ) from last_error

        if last_error:

            raise RuntimeError(
                f"OpenRouter request failed after "
                f"{MAX_RETRIES} attempts: {last_error}"
            ) from last_error

        raise RuntimeError(
            "OpenRouter request failed unexpectedly."
        )

    # ========================================================
    # JSON RESPONSE HELPER
    # ========================================================

    async def generate_json_response(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.2,
    ) -> str:

        return await self.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format={
                "type": "json_object",
            },
        )
