
from pydantic import BaseModel, Field
from typing import Literal


class AIEvaluation(BaseModel):

    # Evaluation scores
    technical_correctness: int | None = Field(
        default=None, ge=0, le=100
    )

    concept_coverage: int | None = Field(
        default=None, ge=0, le=100
    )

    reasoning_quality: int | None = Field(
        default=None, ge=0, le=100
    )

    communication_clarity: int | None = Field(
        default=None, ge=0, le=100
    )

    # Answer classification
    answer_classification: Literal[
        "GOOD",
        "PARTIAL",
        "IRRELEVANT",
        "NO_KNOWLEDGE"
    ] = "PARTIAL"

    # Concept evaluation
    matched_concepts: list[str] = Field(
        default_factory=list
    )

    missing_concepts: list[str] = Field(
        default_factory=list
    )

    # Incorrect claims and supporting evidence
    incorrect_statements: list[str] = Field(
        default_factory=list
    )

    evidence: list[str] = Field(
        default_factory=list
    )

    # Qualitative feedback
    strengths: list[str] = Field(
        default_factory=list
    )

    improvement_areas: list[str] = Field(
        default_factory=list
    )

    overall_feedback: str = (
        "AI evaluation was incomplete. Manual review is recommended."
    )

    confidence: Literal[
        "low",
        "medium",
        "high"
    ] = "low"
