
import os
import httpx

from dotenv import load_dotenv


# Load environment variables
load_dotenv()


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1"
)

OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL")

OPENROUTER_TIMEOUT = float(
    os.getenv("OPENROUTER_TIMEOUT", "60")
)


class OpenRouterClient:

    def __init__(self):

        if not OPENROUTER_API_KEY:
            raise ValueError(
                "OPENROUTER_API_KEY is missing in .env"
            )

        if not OPENROUTER_MODEL:
            raise ValueError(
                "OPENROUTER_MODEL is missing in .env"
            )

        self.url = (
            f"{OPENROUTER_BASE_URL.rstrip('/')}"
            "/chat/completions"
        )

        self.headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        self.timeout = httpx.Timeout(
            OPENROUTER_TIMEOUT,
            connect=15.0
        )

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> str:

        payload = {
            "model": OPENROUTER_MODEL,

            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],

            "temperature": 0.2,
            "max_tokens": 1500
        }

        try:

            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:

                response = await client.post(
                    self.url,
                    headers=self.headers,
                    json=payload
                )

                # Handle HTTP errors
                if response.is_error:

                    raise RuntimeError(
                        f"OpenRouter API error "
                        f"({response.status_code}): "
                        f"{response.text[:1000]}"
                    )

                # Parse JSON response
                try:
                    result = response.json()

                except ValueError as error:

                    raise RuntimeError(
                        "OpenRouter returned invalid JSON."
                    ) from error

                # Validate response structure
                choices = result.get("choices")

                if not isinstance(choices, list) or not choices:
                    raise RuntimeError(
                        "OpenRouter response contains no choices."
                    )

                message = choices[0].get("message", {})

                if not isinstance(message, dict):
                    raise RuntimeError(
                        "Invalid message structure in OpenRouter response."
                    )

                content = message.get("content")

                if not isinstance(content, str):
                    raise RuntimeError(
                        "OpenRouter returned empty or unsupported content."
                    )

                content = content.strip()

                if not content:
                    raise RuntimeError(
                        "OpenRouter returned an empty AI response."
                    )

                return content

        except httpx.TimeoutException as error:

            raise RuntimeError(
                "OpenRouter request timed out. "
                "Please try again."
            ) from error

        except httpx.RequestError as error:

            raise RuntimeError(
                f"Could not connect to OpenRouter: {error}"
            ) from error
