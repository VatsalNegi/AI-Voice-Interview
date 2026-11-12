
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
    "gemini-3.8-flash",
)

DEFAULT_FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
]

GEMINI_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv(
        "GEMINI_FALLBACK_MODELS",
        ",".join(DEFAULT_FALLBACK_MODELS),
    ).split(",")
    if model.strip()
]

GEMINI_TIMEOUT = float(
    os.getenv("GEMINI_TIMEOUT", "120")
)

# Total attempts per model, including the first request.
GEMINI_ATTEMPTS_PER_MODEL = int(
    os.getenv("GEMINI_ATTEMPTS_PER_MODEL", "2")
)

INITIAL_RETRY_DELAY = 0.5

RETRYABLE_STATUS_CODES = {
    408,
    500,
    502,
    503,
    504,
}

API_BASE_URL = (
    "https://generativelanguage.googleapis.com/"
    "v1beta/models"
)


# ============================================================
# GEMINI CLIENT
# ============================================================

class GeminiClient:
    """
    Asynchronous Gemini client with automatic model fallback.

    Features:
    - Multiple Gemini model support
    - Automatic model switching
    - Exponential retry backoff
    - HTTP error handling
    - JSON response support
    - Existing service interface preserved
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

        if GEMINI_ATTEMPTS_PER_MODEL < 1:
            raise ValueError(
                "GEMINI_ATTEMPTS_PER_MODEL must be at least 1."
            )

        # Primary model always gets first priority.
        self.models = list(
            dict.fromkeys(
                [GEMINI_MODEL] + GEMINI_FALLBACK_MODELS
            )
        )

        self.headers = {
            "x-goog-api-key": GEMINI_API_KEY,
            "Content-Type": "application/json",
        }

        self.timeout = httpx.Timeout(
            GEMINI_TIMEOUT,
            connect=15.0,
        )

        logger.info(
            "Gemini client initialized. Models=%s",
            self.models,
        )

    # ========================================================
    # RESPONSE EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_content(result: dict) -> str:

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
    # REQUEST ONE MODEL
    # ========================================================

    async def _request_model(
        self,
        client: httpx.AsyncClient,
        model: str,
        payload: dict,
    ) -> str:

        url = f"{API_BASE_URL}/{model}:generateContent"

        last_error = None

        for attempt in range(
            1,
            GEMINI_ATTEMPTS_PER_MODEL + 1,
        ):

            try:

                logger.info(
                    "Gemini request: model=%s attempt=%s/%s",
                    model,
                    attempt,
                    GEMINI_ATTEMPTS_PER_MODEL,
                )

                response = await client.post(
                    url,
                    headers=self.headers,
                    json=payload,
                )

                status = response.status_code

                # ------------------------------------------------
                # RATE LIMIT / QUOTA
                # ------------------------------------------------

                if status == 429:

                    raise RuntimeError(
                        f"Gemini HTTP 429 for {model}: "
                        f"{response.text[:1000]}"
                    )

                # ------------------------------------------------
                # RETRYABLE SERVER ERRORS
                # ------------------------------------------------

                if status in RETRYABLE_STATUS_CODES:

                    last_error = RuntimeError(
                        f"Gemini HTTP {status} for {model}: "
                        f"{response.text[:1000]}"
                    )

                    logger.warning("%s", last_error)

                    if attempt < GEMINI_ATTEMPTS_PER_MODEL:

                        delay = (
                            INITIAL_RETRY_DELAY
                            * (2 ** (attempt - 1))
                        )

                        logger.info(
                            "Retrying %s in %.2f seconds",
                            model,
                            delay,
                        )

                        await asyncio.sleep(delay)
                        continue

                    raise last_error

                # ------------------------------------------------
                # NON-RETRYABLE HTTP ERRORS
                # ------------------------------------------------

                if response.is_error:

                    raise RuntimeError(
                        f"Gemini HTTP {status} for {model}: "
                        f"{response.text[:1500]}"
                    )

                # ------------------------------------------------
                # PARSE RESPONSE
                # ------------------------------------------------

                try:
                    result = response.json()

                except ValueError as error:

                    raise RuntimeError(
                        f"Gemini returned invalid response JSON "
                        f"from {model}."
                    ) from error

                if not isinstance(result, dict):

                    raise RuntimeError(
                        f"Invalid Gemini response structure from {model}."
                    )

                if result.get("error"):

                    raise RuntimeError(
                        f"Gemini provider error for {model}: "
                        f"{self._extract_error(result)}"
                    )

                content = self._extract_content(result)

                candidates = result.get("candidates", [])

                finish_reason = None

                if candidates and isinstance(candidates[0], dict):

                    finish_reason = candidates[0].get(
                        "finishReason"
                    )

                # ------------------------------------------------
                # EMPTY RESPONSE
                # ------------------------------------------------

                if not content:

                    prompt_feedback = result.get(
                        "promptFeedback",
                        {},
                    )

                    block_reason = (
                        prompt_feedback.get("blockReason")
                        if isinstance(prompt_feedback, dict)
                        else None
                    )

                    raise RuntimeError(
                        f"Gemini returned no usable content. "
                        f"Model={model}, "
                        f"FinishReason={finish_reason}, "
                        f"BlockReason={block_reason}"
                    )

                # ------------------------------------------------
                # TOKEN LIMIT
                # ------------------------------------------------

                if finish_reason == "MAX_TOKENS":

                    raise RuntimeError(
                        f"Gemini response truncated by token limit. "
                        f"Model={model}"
                    )

                # ------------------------------------------------
                # SAFETY BLOCK
                # ------------------------------------------------

                if finish_reason in {
                    "SAFETY",
                    "RECITATION",
                    "BLOCKLIST",
                    "PROHIBITED_CONTENT",
                }:

                    raise RuntimeError(
                        f"Gemini blocked the response. "
                        f"Model={model}, "
                        f"FinishReason={finish_reason}"
                    )

                logger.info(
                    "Gemini request successful. Model=%s",
                    model,
                )

                return content

            except (
                httpx.TimeoutException,
                httpx.RequestError,
            ) as error:

                last_error = error

                logger.warning(
                    "Gemini connection error. Model=%s "
                    "Attempt=%s Error=%s",
                    model,
                    attempt,
                    error,
                )

                if attempt < GEMINI_ATTEMPTS_PER_MODEL:

                    delay = (
                        INITIAL_RETRY_DELAY
                        * (2 ** (attempt - 1))
                    )

                    await asyncio.sleep(delay)
                    continue

                raise RuntimeError(
                    f"Gemini request failed for model {model}: "
                    f"{error}"
                ) from error

        raise RuntimeError(
            f"Gemini model {model} failed: {last_error}"
        )

    # ========================================================
    # GENERATE RESPONSE WITH MODEL FALLBACK
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

        if (
            not isinstance(system_prompt, str)
            or not system_prompt.strip()
        ):
            raise ValueError(
                "System prompt cannot be empty."
            )

        if (
            not isinstance(user_prompt, str)
            or not user_prompt.strip()
        ):
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
        # REQUEST PAYLOAD
        # ----------------------------------------------------

        generation_config = {
            "maxOutputTokens": max_tokens,
        }

        if (
            response_format is not None
            and response_format.get("type") == "json_object"
        ):

            generation_config["responseMimeType"] = (
                "application/json"
            )

        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": system_prompt,
                    }
                ],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": user_prompt,
                        }
                    ],
                }
            ],
            "generationConfig": generation_config,
        }

        # ----------------------------------------------------
        # TRY MODELS IN PRIORITY ORDER
        # ----------------------------------------------------

        errors = []

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:

            for index, model in enumerate(self.models):

                logger.info(
                    "Trying Gemini model %s (%s/%s)",
                    model,
                    index + 1,
                    len(self.models),
                )

                try:

                    return await self._request_model(
                        client=client,
                        model=model,
                        payload=payload,
                    )

                except RuntimeError as error:

                    error_message = str(error)

                    errors.append(
                        f"{model}: {error_message}"
                    )

                    # Do not switch models for authentication,
                    # permission, malformed request or safety errors.
                    if any(
                        marker in error_message
                        for marker in (
                            "HTTP 400",
                            "HTTP 401",
                            "HTTP 403",
                            "blocked the response",
                            "token limit",
                        )
                    ):

                        raise

                    logger.warning(
                        "Gemini model failed. "
                        "Switching from %s if another model exists. "
                        "Reason=%s",
                        model,
                        error_message,
                    )

                    if index < len(self.models) - 1:

                        logger.info(
                            "Switching to next Gemini model."
                        )

                        continue

        raise RuntimeError(
            "All configured Gemini models failed.\n"
            + "\n".join(errors)
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

OpenRouterClient = GeminiClient
