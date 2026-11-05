
import pytest
from unittest.mock import AsyncMock, patch

from app.services.hybrid_evaluator import HybridEvaluator
from app.schemas.ai_evaluation import AIEvaluation


QUESTION = {
    "question_id": "PY_001",
    "question": "Explain the difference between a Python list and tuple.",
    "expected_concepts": [
        "List is mutable",
        "Tuple is immutable",
        "Lists use square brackets",
        "Tuples use parentheses"
    ]
}


TEST_CASES = [
    {
        "name": "Correct Answer",
        "answer": """
        Lists are mutable, so we can modify them.
        Tuples are immutable, so their elements cannot be reassigned.
        Lists use square brackets and tuples use parentheses.
        """,
        "expected_contradiction": False
    },

    {
        "name": "Incorrect Answer",
        "answer": """
        Lists are immutable, so we cannot modify them.
        Tuples are mutable, so we can change their elements.
        Lists use square brackets and tuples use parentheses.
        """,
        "expected_contradiction": False
    },

    {
        "name": "Correct Paraphrased Answer",
        "answer": """
        I can append, remove, or update items in a list after
        creating it.
        Once a tuple is created, its existing elements cannot
        be replaced.
        Lists are written using square brackets, while tuples
        are written using parentheses.
        """,
        "expected_contradiction": False
    },

    {
        "name": "Contradictory Answer",
        "answer": """
        Lists are mutable, so we can modify them.
        However, lists are immutable and cannot be changed.
        Tuples are immutable.
        Lists use square brackets and tuples use parentheses.
        """,
        "expected_contradiction": True
    }
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "test_case",
    TEST_CASES,
    ids=lambda case: case["name"]
)
async def test_hybrid_scenarios(test_case):

    evaluator = HybridEvaluator()

    mock_ai_result = AIEvaluation(
        technical_correctness=85,
        concept_coverage=80,
        reasoning_quality=85,
        communication_clarity=90,
        matched_concepts=["Tuple is immutable"],
        missing_concepts=["List is mutable"],
        incorrect_statements=[],
        evidence=[],
        strengths=["Some concepts explained correctly"],
        improvement_areas=["Clarify mutability"],
        overall_feedback="Evaluation completed successfully.",
        confidence="medium"
    )

    with patch.object(
        evaluator.ai_evaluator,
        "evaluate_answer",
        new_callable=AsyncMock,
        return_value=mock_ai_result
    ) as mock_ai:

        result = await evaluator.evaluate_answer(
            question=QUESTION,
            candidate_answer=test_case["answer"]
        )

    assert "rule_evaluation" in result
    assert "semantic_evaluation" in result

    contradiction_result = result["contradiction_evaluation"]

    assert (
        contradiction_result["has_contradictions"]
        == test_case["expected_contradiction"]
    )

    assert isinstance(
        result["ai_evaluation_triggered"],
        bool
    )

    if result["ai_evaluation_triggered"]:
        mock_ai.assert_awaited_once()

    print(f"\nPassed: {test_case['name']}")
