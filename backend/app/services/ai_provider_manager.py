
import logging

from app.services.openrouter_client import GeminiClient
from app.services.groq_client import GroqClient
from app.services.openrouter_llm_client import OpenRouterLLMClient

logger = logging.getLogger(__name__)


class AIProviderManager:
    """
    Central AI provider manager.

    Priority:
    1. Gemini
    2. Groq
    3. OpenRouter
    """

    def __init__(self):
        self.last_provider = None

        self.providers = [
            ("Gemini", GeminiClient),
            ("Groq", GroqClient),
            ("OpenRouter", OpenRouterLLMClient),
        ]

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

        errors = []

        for provider_name, provider_class in self.providers:

            try:
                logger.info("Trying AI provider: %s", provider_name)

                client = provider_class()

                response = await client.generate_response(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format=response_format,
                )

                self.last_provider = provider_name

                logger.info(
                    "AI generation successful. Provider=%s",
                    provider_name,
                )

                return response

            except Exception as error:
                error_message = str(error)

                errors.append(
                    f"{provider_name}: {error_message}"
                )

                logger.exception(
                    "AI provider failed: %s",
                    provider_name,
                )

        self.last_provider = None

        raise RuntimeError(
            "All AI providers failed.\n" + "\n".join(errors)
        )

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
