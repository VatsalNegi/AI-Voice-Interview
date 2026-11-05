import os
import httpx
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

headers = {
    "xi-api-key": API_KEY,
    "Content-Type": "application/json",
    "Accept": "audio/mpeg"
}

payload = {
    "text": (
        "Hello! Welcome to your AI interview. "
        "I am your interviewer today. "
        "Let's begin with a brief introduction."
    ),
    "model_id": "eleven_flash_v2_5"
}

try:
    response = httpx.post(
        url,
        headers=headers,
        params={"output_format": "mp3_22050_32"},
        json=payload,
        timeout=90
    )

    print("HTTP Status:", response.status_code)

    if response.is_error:
        print("Error:", response.text)
    else:
        with open("custom_voice_test.mp3", "wb") as file:
            file.write(response.content)

        print("SUCCESS! Audio generated.")
        print("Saved as: custom_voice_test.mp3")

except Exception as error:
    print("Error:", str(error))