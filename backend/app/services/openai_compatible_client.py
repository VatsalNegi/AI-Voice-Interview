
import logging
import os

import httpx

logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    """Shared asynchronous client for OpenAI-compatible APIs."""

    def __init__(
        self,
        provider_name: str,
        api_key: str | None,
        base_url: str,
        model: str,
        timeout: float = 120.0,
        token_parameter: str = "max_tokens",
    ):
        if not api_key:
            raise ValueError(f"{provider_name} API key is missing.")

        if not model:
            raise ValueError(f"{provider_name} model is missing.")

        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = httpx.Timeout(timeout, connect=15.0)
        self.token_parameter = token_parameter

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
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            self.token_parameter: max_tokens,
            "temperature": temperature,
        }

        if response_format and response_format.get("type") == "json_object":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                )

            if response.is_error:
                raise RuntimeError(
                    f"{self.provider_name} HTTP {response.status_code}: "
                    f"{response.text[:1500]}"
                )

            try:
                result = response.json()
            except ValueError as error:
                raise RuntimeError(
                    f"{self.provider_name} returned invalid JSON."
                ) from error

            choices = result.get("choices", [])

            if not choices or not isinstance(choices[0], dict):
                raise RuntimeError(
                    f"{self.provider_name} returned no completion choices."
                )

            message = choices[0].get("message", {})
            content = message.get("content")

            if isinstance(content, list):
                content = "".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict)
                )

            if not isinstance(content, str) or not content.strip():
                raise RuntimeError(
                    f"{self.provider_name} returned empty content."
                )

            finish_reason = choices[0].get("finish_reason")

            if finish_reason == "length":
                raise RuntimeError(
                    f"{self.provider_name} response was truncated "
                    "because of the token limit."
                )

            logger.info(
                "%s generation successful. Model=%s",
                self.provider_name,
                self.model,
            )

            return content.strip()

        except httpx.TimeoutException as error:
            raise RuntimeError(
                f"{self.provider_name} request timed out."
            ) from error

        except httpx.RequestError as error:
            raise RuntimeError(
                f"{self.provider_name} connection failed: {error}"
            ) from error

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
            response_format={"type": "json_object"},
        )
