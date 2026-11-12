
import os

from dotenv import load_dotenv

from app.services.openai_compatible_client import OpenAICompatibleClient

load_dotenv()


class GroqClient(OpenAICompatibleClient):

    def __init__(self):
        super().__init__(
            provider_name="Groq",
            api_key=os.getenv("GROQ_API_KEY"),
            base_url=os.getenv(
                "GROQ_BASE_URL",
                "https://api.groq.com/openai/v1",
            ),
            model=os.getenv(
                "GROQ_MODEL",
                "openai/gpt-oss-20b",
            ),
            timeout=float(os.getenv("GROQ_TIMEOUT", "120")),
            token_parameter="max_completion_tokens",
        )
