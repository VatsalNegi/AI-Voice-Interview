
import asyncio
from app.services.openrouter_client import GeminiClient


async def main():
    client = GeminiClient()

    print("Configured models:", client.models)
    print("\nTesting Gemini connection...")

    try:
        response = await client.generate_response(
            system_prompt="You are a helpful assistant.",
            user_prompt="Reply with exactly: Gemini connection successful",
            max_tokens=256,
            temperature=0.2,
        )

        print("\nSUCCESS!")
        print("Response:", response)

    except Exception as error:
        print("\nFAILED!")
        print("Error:", error)


if __name__ == "__main__":
    asyncio.run(main())
