
import asyncio
from app.services.ai_provider_manager import AIProviderManager as OpenRouterClient


async def main():
    client = OpenRouterClient()

    try:
        response = await client.generate_json_response(
            system_prompt="You are a helpful assistant. Return valid JSON only.",
            user_prompt='Return this JSON: {"candidate_type": "fresher", "reason": "No full-time experience"}',
            max_tokens=300,
            temperature=0.1,
        )

        print("\nSUCCESS!")
        print("OpenRouter response:")
        print(response)

    except Exception as error:
        print("\nFAILED!")
        print(type(error).__name__, str(error))


if __name__ == "__main__":
    asyncio.run(main())
