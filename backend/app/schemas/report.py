
from pydantic import BaseModel, Field
from typing import List, Optional


class CompetencyScore(BaseModel):
    competency: str

    # None until genuine rubric-based evaluation is implemented.
    score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100
    )

    weight: float = Field(ge=0, le=100)

    evidence: List[str] = Field(default_factory=list)

    feedback: str


class QuestionEvaluation(BaseModel):
    question_id: str
    question: str
    competency: str
    candidate_answer: str

    # Measures expected-concept coverage, not technical correctness.
    concept_coverage: float = Field(ge=0, le=100)

    strengths: List[str] = Field(default_factory=list)

    improvement_areas: List[str] = Field(default_factory=list)

    technical_feedback: str


class InterviewReport(BaseModel):
    session_id: str
    candidate_id: str
    candidate_name: str
    email: str
    job_role: str

    # Actual overall skill score remains unavailable for now.
    overall_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100
    )

    recommendation: str
    recommendation_reason: str

    competency_scores: List[CompetencyScore] = Field(
        default_factory=list
    )

    question_evaluations: List[QuestionEvaluation] = Field(
        default_factory=list
    )

    overall_strengths: List[str] = Field(
        default_factory=list
    )

    areas_for_improvement: List[str] = Field(
        default_factory=list
    )

    summary: str

    transcript: List[dict] = Field(
        default_factory=list
    )

    generated_at: str
