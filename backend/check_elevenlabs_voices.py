
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ELEVENLABS_API_KEY")

if not api_key:
    print("ERROR: ELEVENLABS_API_KEY not found.")
    raise SystemExit(1)

response = httpx.get(
    "https://api.elevenlabs.io/v1/voices",
    headers={"xi-api-key": api_key},
    timeout=30
)

print("HTTP Status:", response.status_code)

if response.is_error:
    print(response.text)
    raise SystemExit(1)

data = response.json()

print("\nAVAILABLE VOICES:\n")

for voice in data.get("voices", []):
    print(
        "Name:", voice.get("name"),
        "| ID:", voice.get("voice_id"),
        "| Category:", voice.get("category")
    )
