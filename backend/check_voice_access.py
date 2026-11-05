import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

if not API_KEY or not VOICE_ID:
    raise SystemExit("Missing API key or voice ID in .env")

url = f"https://api.elevenlabs.io/v1/voices/{VOICE_ID}"

response = httpx.get(
    url,
    headers={"xi-api-key": API_KEY},
    timeout=30
)

print("HTTP Status:", response.status_code)

if response.is_error:
    print(response.text)
    raise SystemExit(1)

data = response.json()

print("\nVOICE DETAILS")
print("Name:", data.get("name"))
print("Category:", data.get("category"))
print("Available for tiers:", data.get("available_for_tiers"))
print("Sharing:", data.get("sharing"))