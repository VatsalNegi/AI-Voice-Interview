
import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"


async def main():

    print("\n====================================")
    print("       GROQ COMPLETION TEST")
    print("====================================")

    # 1. Check API key

    if not API_KEY:
        print("[FAILED] GROQ_API_KEY missing.")
        return

    print("[PASSED] Groq API key loaded.")

    # 2. Prepare request

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a technical interview assistant. "
                    "Follow the user's instructions precisely."
                )
            },
            {
                "role": "user",
                "content": (
                    "Explain Python decorators in exactly 3 sentences."
                )
            }
        ],
        "max_completion_tokens": 1024,
        "temperature": 0.2
    }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # 3. Send API request

    try:

        async with httpx.AsyncClient(timeout=60) as client:

            response = await client.post(
                BASE_URL,
                headers=headers,
                json=payload
            )

        print("\nHTTP Status:", response.status_code)

        if response.status_code != 200:
            print("[FAILED] Groq API request failed.")
            print("Response:", response.text[:1500])
            return

        print("[PASSED] Groq API connection successful.")

        # 4. Parse response

        result = response.json()

        choices = result.get("choices", [])

        if not choices:
            print("[FAILED] No completion choices returned.")
            return

        message = choices[0].get("message", {})
        content = message.get("content")

        if isinstance(content, list):
            content = "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict)
            )

        if not isinstance(content, str) or not content.strip():
            print("[FAILED] Empty model response.")
            return

        print("[PASSED] Model generated a response.")

        # 5. Display generated response

        print("\nModel:", MODEL)
        print("\nGroq Response:\n")
        print(content)

        # 6. Check sentence count

        sentences = [
            sentence.strip()
            for sentence in content.split(".")
            if sentence.strip()
        ]

        print("\nDetected sentences:", len(sentences))

        if len(sentences) == 3:
            print("[PASSED] Exactly 3 sentences returned.")
        else:
            print(
                "[WARNING] Expected 3 sentences, "
                f"received approximately {len(sentences)}."
            )

        print("\n====================================")
        print("       GROQ TEST COMPLETED")
        print("====================================")

    except httpx.TimeoutException:
        print("[FAILED] Groq request timed out.")

    except httpx.RequestError as error:
        print("[FAILED] Network error:", str(error))

    except Exception as error:
        print("[FAILED] Unexpected error:", str(error))


if __name__ == "__main__":
    asyncio.run(main())
