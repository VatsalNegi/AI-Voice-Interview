
import asyncio
import logging

from app.services.ai_provider_manager import AIProviderManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


async def main():

    manager = AIProviderManager()

    print("\nTesting AI Provider Manager...")
    print("Priority: Gemini -> Groq -> OpenRouter\n")

    try:
        response = await manager.generate_response(
            system_prompt=(
                "You are a concise technical interviewer. "
                "Answer accurately in simple English."
            ),
            user_prompt=(
                "Explain Python decorators in three sentences. "
                "Include one practical use case."
            ),
            max_tokens=512,
            temperature=0.2,
        )

        print("\n========== TEST RESULT ==========")
        print("Status: SUCCESS")
        print("Provider:", manager.last_provider)
        print("\nGenerated Response:\n")
        print(response)

    except Exception as error:
        print("\n========== TEST RESULT ==========")
        print("Status: FAILED")
        print("Error:", error)


if __name__ == "__main__":
    asyncio.run(main())
