
import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


async def main():
    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY is missing.")
        return

    url = "https://api.groq.com/openai/v1/models"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=headers)

        print("HTTP Status:", response.status_code)

        if response.status_code != 200:
            print("Groq API error:", response.text[:1000])
            return

        data = response.json()

        print("\nAvailable Groq models:\n")

        for model in data.get("data", []):
            if model.get("active", True):
                print("-", model["id"])


if __name__ == "__main__":
    asyncio.run(main())
