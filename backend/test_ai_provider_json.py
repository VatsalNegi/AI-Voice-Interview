
import asyncio
import json
import logging

from app.services.ai_provider_manager import AIProviderManager

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s",
)


async def main():
    manager = AIProviderManager()

    try:
        response = await manager.generate_json_response(
            system_prompt=(
                "You are an interview assessment assistant. "
                "Return only valid JSON."
            ),
            user_prompt=(
                "Create an assessment for a Python developer. "
                "Return this structure: "
                '{"skill": "string", "difficulty": "string", '
                '"questions": ["string", "string", "string"]}'
            ),
            max_tokens=1024,
            temperature=0.2,
        )

        parsed = json.loads(response)

        print("\n========== JSON TEST ==========")
        print("Status: SUCCESS")
        print("Provider:", manager.last_provider)
        print("\nParsed JSON:")
        print(json.dumps(parsed, indent=4))

    except Exception as error:
        print("\nJSON TEST FAILED:", error)


if __name__ == "__main__":
    asyncio.run(main())
