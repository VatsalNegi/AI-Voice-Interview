
import os
import asyncio
import logging
import httpx

from dotenv import load_dotenv

# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)

GEMINI_TIMEOUT = float(
    os.getenv("GEMINI_TIMEOUT", "120")
)

MAX_RETRIES = 3

RETRYABLE_STATUS_CODES = {
    408,
    500,
    502,
    503,
    504,
}


# ============================================================
# GEMINI CLIENT
# ============================================================

class GeminiClient:
    """
    Reusable asynchronous Gemini API client.

    Supports:
    - Resume analysis
    - Job description analysis
    - Interview question generation
    - Candidate answer evaluation
    - JSON responses
    - Automatic retries
    - Provider error handling
    """

    def __init__(self):

        if not GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY is missing in backend/.env"
            )

        if not GEMINI_MODEL:
            raise ValueError(
                "GEMINI_MODEL is missing in backend/.env"
            )

        self.model = GEMINI_MODEL

        self.url = (
            "https://generativelanguage.googleapis.com/"
            f"v1beta/models/{self.model}:generateContent"
        )

        self.headers = {
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        }

        self.timeout = httpx.Timeout(
            GEMINI_TIMEOUT,
            connect=15.0,
        )

    # ========================================================
    # RESPONSE CONTENT EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_content(result: dict) -> str:
        """
        Extract text from Gemini response candidates.
        """

        candidates = result.get("candidates", [])

        if not isinstance(candidates, list) or not candidates:
            return ""

        candidate = candidates[0]

        if not isinstance(candidate, dict):
            return ""

        content = candidate.get("content", {})

        if not isinstance(content, dict):
            return ""

        parts = content.get("parts", [])

        if not isinstance(parts, list):
            return ""

        text_parts = []

        for part in parts:

            if not isinstance(part, dict):
                continue

            text_value = part.get("text")

            if isinstance(text_value, str):
                text_parts.append(text_value)

        return "".join(text_parts).strip()

    # ========================================================
    # ERROR EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_error(result: dict) -> str:

        error = result.get("error", {})

        if isinstance(error, dict):

            return str(
                error.get("message")
                or error.get("status")
                or error
            )

        return str(error or "Unknown Gemini API error")

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

        # ----------------------------------------------------
        # INPUT VALIDATION
        # ----------------------------------------------------

        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError(
                "System prompt cannot be empty."
            )

        if not isinstance(user_prompt, str) or not user_prompt.strip():
            raise ValueError(
                "User prompt cannot be empty."
            )

        if max_tokens < 1:
            raise ValueError(
                "max_tokens must be greater than zero."
            )

        if not 0 <= temperature <= 2:
            raise ValueError(
                "temperature must be between 0 and 2."
            )

        # ----------------------------------------------------
        # GEMINI REQUEST PAYLOAD
        # ----------------------------------------------------

        generation_config = {
            "maxOutputTokens": max_tokens,
        }

        # Gemini 3.x uses its own sampling behavior.
        # Temperature is intentionally not sent.

        if response_format is not None:

            if response_format.get("type") == "json_object":

                generation_config["responseMimeType"] = (
                    "application/json"
                )

        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": system_prompt
                    }
                ]
            },

            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": user_prompt
                        }
                    ]
                }
            ],

            "generationConfig": generation_config,
        }

        last_error = None

        # ====================================================
        # HTTP CLIENT
        # ====================================================

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:

            for attempt in range(
                1,
                MAX_RETRIES + 1
            ):

                try:

                    logger.info(
                        "Gemini request: model=%s attempt=%s/%s",
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
                    # RATE LIMIT HANDLING
                    # ----------------------------------------

                    if response.status_code == 429:

                        raise RuntimeError(
                            "Gemini API rate limit or quota exceeded. "
                            "Check your Google AI Studio usage and quota."
                        )

                    # ----------------------------------------
                    # RETRYABLE HTTP ERRORS
                    # ----------------------------------------

                    if response.status_code in RETRYABLE_STATUS_CODES:

                        last_error = RuntimeError(
                            f"Gemini HTTP {response.status_code}: "
                            f"{response.text[:1000]}"
                        )

                        logger.warning(
                            "%s",
                            last_error
                        )

                        if attempt < MAX_RETRIES:

                            delay = 2 ** attempt

                            logger.info(
                                "Retrying Gemini in %s seconds.",
                                delay,
                            )

                            await asyncio.sleep(delay)

                            continue

                        break

                    # ----------------------------------------
                    # OTHER HTTP ERRORS
                    # ----------------------------------------

                    if response.is_error:

                        raise RuntimeError(
                            f"Gemini HTTP error "
                            f"{response.status_code}: "
                            f"{response.text[:1500]}"
                        )

                    # ----------------------------------------
                    # RESPONSE JSON VALIDATION
                    # ----------------------------------------

                    try:

                        result = response.json()

                    except ValueError as error:

                        raise RuntimeError(
                            "Gemini returned invalid response JSON."
                        ) from error

                    if not isinstance(result, dict):

                        raise RuntimeError(
                            "Invalid Gemini response structure."
                        )

                    # ----------------------------------------
                    # PROVIDER ERROR VALIDATION
                    # ----------------------------------------

                    provider_error = self._extract_error(
                        result
                    )

                    if result.get("error"):

                        raise RuntimeError(
                            f"Gemini provider error: {provider_error}"
                        )

                    # ----------------------------------------
                    # CONTENT EXTRACTION
                    # ----------------------------------------

                    content = self._extract_content(
                        result
                    )

                    candidates = result.get(
                        "candidates",
                        []
                    )

                    finish_reason = None

                    if candidates and isinstance(candidates[0], dict):

                        finish_reason = candidates[0].get(
                            "finishReason"
                        )

                    # ----------------------------------------
                    # EMPTY RESPONSE HANDLING
                    # ----------------------------------------

                    if not content:

                        prompt_feedback = result.get(
                            "promptFeedback",
                            {}
                        )

                        block_reason = (
                            prompt_feedback.get("blockReason")
                            if isinstance(prompt_feedback, dict)
                            else None
                        )

                        raise RuntimeError(
                            "Gemini returned no usable content. "
                            f"Model={self.model}, "
                            f"FinishReason={finish_reason}, "
                            f"BlockReason={block_reason}"
                        )

                    # ----------------------------------------
                    # TOKEN LIMIT VALIDATION
                    # ----------------------------------------

                    if finish_reason == "MAX_TOKENS":

                        raise RuntimeError(
                            "Gemini response was truncated because "
                            "the token limit was reached. "
                            "Increase max_tokens."
                        )

                    # ----------------------------------------
                    # BLOCKED RESPONSE VALIDATION
                    # ----------------------------------------

                    if finish_reason in {
                        "SAFETY",
                        "RECITATION",
                        "BLOCKLIST",
                        "PROHIBITED_CONTENT",
                    }:

                        raise RuntimeError(
                            "Gemini blocked the response. "
                            f"FinishReason={finish_reason}"
                        )

                    # ----------------------------------------
                    # SUCCESS
                    # ----------------------------------------

                    logger.info(
                        "Gemini request successful. "
                        "Model=%s FinishReason=%s",
                        self.model,
                        finish_reason,
                    )

                    return content

                # --------------------------------------------
                # TIMEOUT HANDLING
                # --------------------------------------------

                except httpx.TimeoutException as error:

                    last_error = error

                    logger.warning(
                        "Gemini timeout on attempt %s/%s.",
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
                        "Gemini network error on attempt %s/%s: %s",
                        attempt,
                        MAX_RETRIES,
                        error,
                    )

                    if attempt < MAX_RETRIES:

                        await asyncio.sleep(2 ** attempt)

                        continue

                except RuntimeError:
                    raise

        # ====================================================
        # FINAL ERROR HANDLING
        # ====================================================

        if isinstance(last_error, httpx.TimeoutException):

            raise RuntimeError(
                f"Gemini request timed out after "
                f"{MAX_RETRIES} attempts. "
                f"Configured timeout: {GEMINI_TIMEOUT} seconds."
            ) from last_error

        if isinstance(last_error, httpx.RequestError):

            raise RuntimeError(
                f"Could not connect to Gemini after "
                f"{MAX_RETRIES} attempts: {last_error}"
            ) from last_error

        if last_error:

            raise RuntimeError(
                f"Gemini request failed after "
                f"{MAX_RETRIES} attempts: {last_error}"
            ) from last_error

        raise RuntimeError(
            "Gemini request failed unexpectedly."
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


# ============================================================
# BACKWARD COMPATIBILITY
# ============================================================

# Existing services can continue importing OpenRouterClient.
OpenRouterClient = GeminiClient
