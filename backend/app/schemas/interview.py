
from pydantic import BaseModel, Field
from typing import Optional


class CandidateContext(BaseModel):
    candidate_id: str
    candidate_name: str
    email: str

    resume_text: str
    job_role: str
    job_description: str


class InterviewSessionCreate(BaseModel):
    candidate: CandidateContext

    interview_duration: int = Field(
        default=30,
        ge=5,
        le=120
    )

    language: str = "English"


class InterviewSessionResponse(BaseModel):
    session_id: str
    candidate_name: str
    job_role: str
    status: str
    current_stage: str


class CandidateAnswerSubmit(BaseModel):
    answer_text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Candidate's answer to the current interview question"
    )
