
from pydantic import BaseModel, Field


class SpeechRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=3000
    )
