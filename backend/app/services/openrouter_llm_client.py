
import os

from dotenv import load_dotenv

from app.services.openai_compatible_client import OpenAICompatibleClient

load_dotenv()


class OpenRouterLLMClient(OpenAICompatibleClient):

    def __init__(self):
        super().__init__(
            provider_name="OpenRouter",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=os.getenv(
                "OPENROUTER_BASE_URL",
                "https://openrouter.ai/api/v1",
            ),
            model=os.getenv(
                "OPENROUTER_MODEL",
                "openrouter/free",
            ),
            timeout=float(os.getenv("OPENROUTER_TIMEOUT", "120")),
            token_parameter="max_tokens",
        )
