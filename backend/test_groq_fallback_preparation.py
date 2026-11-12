import runpy
import logging

import app.services.ai_provider_manager as manager_module
from app.services.groq_client import GroqClient
from app.services.openrouter_llm_client import OpenRouterLLMClient


logging.basicConfig(level=logging.INFO)


# Simulate Gemini being unavailable.
# This does not modify your actual Gemini client or API key.

class ForcedGeminiFailure:

    async def generate_response(self, **kwargs):
        raise RuntimeError(
            "TEST ONLY: Simulated Gemini failure to verify fallback."
        )


# Replace Gemini temporarily in the manager module.
manager_module.GeminiClient = ForcedGeminiFailure


# Preserve the original manager initialization.
original_init = manager_module.AIProviderManager.__init__


def test_provider_init(self):
    original_init(self)

    # Keep production priority unchanged.
    # Gemini fails deliberately, so Groq should be selected.
    self.providers = [
        ("Gemini", manager_module.GeminiClient),
        ("Groq", GroqClient),
        ("OpenRouter", OpenRouterLLMClient),
    ]


manager_module.AIProviderManager.__init__ = test_provider_init


print("\n========================================")
print(" TESTING GROQ FALLBACK")
print("========================================")
print("Gemini: Simulated failure")
print("Groq: Real API")
print("OpenRouter: Secondary fallback")
print("========================================\n")


# Execute the existing full preparation test.
# Its candidate creation, validation, persistence
# and cleanup logic remain unchanged.

runpy.run_path(
    "test_gemini_preparation.py",
    run_name="__main__"
)