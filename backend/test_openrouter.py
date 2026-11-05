
import asyncio

from app.services.openrouter_client import OpenRouterClient


async def main():
    print("Testing OpenRouter connection...")

    try:
        client = OpenRouterClient()

        response = await client.generate_response(
            system_prompt=(
                "You are a technical interviewer. "
                "Return only valid JSON."
            ),
            user_prompt="""
Evaluate this answer.

Question:
What is the difference between a Python list and tuple?

Expected concepts:
- List is mutable
- Tuple is immutable
- Lists use square brackets
- Tuples commonly use parentheses

Candidate answer:
A list is mutable, whereas a tuple is immutable.

Return exactly this JSON structure:
{
    "technical_correctness": 90,
    "concept_coverage": 75,
    "reasoning_quality": 80,
    "communication_clarity": 85,
    "matched_concepts": ["List is mutable", "Tuple is immutable"],
    "missing_concepts": ["Syntax differences"],
    "incorrect_statements": [],
    "evidence": ["A list is mutable", "a tuple is immutable"],
    "strengths": ["Correctly explained mutability"],
    "improvement_areas": ["Explain syntax differences"],
    "overall_feedback": "Good answer.",
    "confidence": "high"
}
"""
        )

        print("\nSUCCESS: OpenRouter returned a response.")
        print("\nRAW MODEL RESPONSE:")
        print(response)

    except Exception as error:
        print("\nOPENROUTER TEST FAILED")
        print("Error type:", type(error).__name__)
        print("Error details:", str(error))


if __name__ == "__main__":
    asyncio.run(main())
