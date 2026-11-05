
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

ELEVENLABS_MODEL_ID = os.getenv(
    "ELEVENLABS_MODEL_ID",
    "eleven_flash_v2_5"
)

ELEVENLABS_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID",
    "w2VczpnpJO48HDyBg1xV"
)

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"


class TTSService:

    @staticmethod
    async def generate_speech(text: str) -> tuple[bytes, str | None]:

        if not ELEVENLABS_API_KEY:
            raise RuntimeError(
                "ELEVENLABS_API_KEY is missing in backend .env"
            )

        if not text or not text.strip():
            raise RuntimeError("Speech text cannot be empty.")

        url = (
            f"{ELEVENLABS_BASE_URL}/text-to-speech/"
            f"{ELEVENLABS_VOICE_ID}"
        )

        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }

        payload = {
            "text": text.strip(),
            "model_id": ELEVENLABS_MODEL_ID,
            "voice_settings": {
                "stability": 0.55,
                "similarity_boost": 0.80,
                "style": 0.20,
                "use_speaker_boost": True
            }
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(
                    90.0,
                    connect=15.0
                )
            ) as client:

                response = await client.post(
                    url,
                    headers=headers,
                    params={
                        "output_format": "mp3_44100_128"
                    },
                    json=payload
                )

                if response.is_error:
                    raise RuntimeError(
                        f"ElevenLabs TTS error "
                        f"({response.status_code}): "
                        f"{response.text[:1500]}"
                    )

                if not response.content:
                    raise RuntimeError(
                        "ElevenLabs returned empty audio."
                    )

                return response.content, None

        except httpx.TimeoutException as error:
            raise RuntimeError(
                "ElevenLabs voice generation timed out."
            ) from error

        except httpx.RequestError as error:
            raise RuntimeError(
                f"Could not connect to ElevenLabs: {error}"
            ) from error
