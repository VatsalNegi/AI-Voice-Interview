
import asyncio
import json

from app.services.ai_provider_manager import AIProviderManager as OpenRouterClient


async def main():
    client = OpenRouterClient()

    result = await client.generate_json_response(
        system_prompt="You are an interview preparation assistant.",
        user_prompt=(
            "Classify this candidate as fresher or experienced. "
            "Candidate has academic projects but no full-time experience. "
            "Return JSON with candidate_type and reason."
        ),
    )

    print("Gemini response:")
    print(result)

    parsed = json.loads(result)
    print("\nParsed JSON:")
    print(parsed)


if __name__ == "__main__":
    asyncio.run(main())
