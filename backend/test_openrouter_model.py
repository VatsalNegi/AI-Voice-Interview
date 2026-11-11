
import os
import asyncio
import json
import httpx

from dotenv import load_dotenv


# Load existing environment variables without modifying .env
load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1",
)

TEST_MODEL = "openrouter/free"


async def test_model():

    if not API_KEY:
        print("ERROR: OPENROUTER_API_KEY not found.")
        return

    url = f"{BASE_URL.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5173",
        "X-Title": "AI Voice Interview Model Test",
    }

    payload = {
        "model": TEST_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful AI assistant. "
                    "Always return valid JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Analyze this candidate profile: "
                    "Python, FastAPI, React, PostgreSQL. "
                    "The candidate has completed two internships "
                    "and three academic projects. "
                    "Classify the candidate as fresher, experienced, "
                    "or uncertain. Return JSON with candidate_type, "
                    "reason, and technical_skills."
                ),
            },
        ],
        "temperature": 0.2,
        "max_tokens": 500,
        "response_format": {
            "type": "json_object"
        },
    }

    timeout = httpx.Timeout(120.0, connect=15.0)

    print("\nTesting OpenRouter model:", TEST_MODEL)
    print("Sending request...\n")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:

            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )

            if response.is_error:
                print("API ERROR:", response.status_code)
                print(response.text[:2000])
                return

            result = response.json()

            print("REQUEST SUCCESSFUL")
            print("Actual model:", result.get("model", "Not provided"))

            choices = result.get("choices", [])

            if not choices:
                print("ERROR: No choices returned.")
                return

            content = choices[0].get("message", {}).get("content")

            if not content:
                print("ERROR: Empty response.")
                return

            # Validate the returned JSON
            parsed = json.loads(content)

            print("\nVALID JSON RESPONSE")
            print(json.dumps(parsed, indent=4))

            print("\nTEST PASSED")

    except httpx.TimeoutException:
        print("TIMEOUT: The model did not respond within 120 seconds.")

    except httpx.RequestError as error:
        print("NETWORK ERROR:", error)

    except json.JSONDecodeError:
        print("INVALID JSON returned by the model.")
        print("Raw response:", content)

    except Exception as error:
        print("UNEXPECTED ERROR:", error)


if __name__ == "__main__":
    asyncio.run(test_model())
