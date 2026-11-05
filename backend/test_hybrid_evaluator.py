
import pytest
from unittest.mock import AsyncMock, patch

from app.services.hybrid_evaluator import HybridEvaluator
from app.schemas.ai_evaluation import AIEvaluation


@pytest.fixture
def question():
    return {
        "question_id": "PY_001",
        "question": "Explain the difference between a Python list and tuple.",
        "expected_concepts": [
            "List is mutable",
            "Tuple is immutable",
            "Lists use square brackets",
            "Tuples use parentheses"
        ]
    }


@pytest.mark.asyncio
async def test_hybrid_evaluator_correct_answer(question):

    evaluator = HybridEvaluator()

    answer = """
    Lists are mutable, so we can modify them.
    Tuples are immutable, so their elements cannot be reassigned.
    Lists use square brackets and tuples use parentheses.
    """

    mock_ai_result = AIEvaluation(
        technical_correctness=95,
        concept_coverage=100,
        reasoning_quality=90,
        communication_clarity=95,
        matched_concepts=question["expected_concepts"],
        missing_concepts=[],
        incorrect_statements=[],
        evidence=[
            "Lists are mutable, so we can modify them.",
            "Tuples are immutable, so their elements cannot be reassigned."
        ],
        strengths=["Correct explanation"],
        improvement_areas=[],
        overall_feedback="The candidate explained the concepts correctly.",
        confidence="high"
    )

    with patch.object(
        evaluator.ai_evaluator,
        "evaluate_answer",
        new_callable=AsyncMock,
        return_value=mock_ai_result
    ) as mock_ai:

        result = await evaluator.evaluate_answer(
            question=question,
            candidate_answer=answer
        )

    assert "rule_evaluation" in result
    assert "semantic_evaluation" in result
    assert "contradiction_evaluation" in result

    assert result["ai_evaluation_successful"] is True

    if result["ai_evaluation_triggered"]:
        mock_ai.assert_awaited_once()

    print("\nHybrid evaluation test passed.")
