
import asyncio
import json

from app.services.openrouter_client import OpenRouterClient


async def main():

    ai = OpenRouterClient()

    question = "What is the difference between a Python list and tuple?"

    expected_concepts = [
        "List is mutable",
        "Tuple is immutable",
        "Lists use square brackets",
        "Tuples use parentheses"
    ]

    candidate_answer = """
Both lists and tuples are mutable.
We can modify elements in both of them.
Lists use parentheses and tuples use square brackets.
Tuples are generally used when we need to frequently
add and remove elements.
"""

    system_prompt = """
    You are an expert technical interviewer.

    Evaluate candidate answers objectively.

    Rules:
    1. Check technical correctness, not just keyword matching.
    2. Recognize conceptually correct paraphrases.
    3. Identify incorrect technical statements.
    4. Identify missing expected concepts.
    5. Evaluate reasoning and clarity.
    6. Never invent evidence that the candidate did not provide.
    7. Do not make hiring decisions.

    Return ONLY valid JSON using this structure:

    {
        "technical_correctness": 0,
        "concept_coverage": 0,
        "reasoning_quality": 0,
        "communication_clarity": 0,
        "matched_concepts": [],
        "missing_concepts": [],
        "incorrect_statements": [],
        "evidence": [],
        "strengths": [],
        "improvement_areas": [],
        "overall_feedback": "",
        "confidence": "low"
    }

    All scores must be between 0 and 100.
    Confidence must be low, medium, or high.
    """

    user_prompt = f"""
    Interview Question:
    {question}

    Expected Concepts:
    {json.dumps(expected_concepts, indent=2)}

    Candidate Answer:
    {candidate_answer}

    Evaluate this answer using the required JSON structure.
    """

    response = await ai.generate_response(
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )

    print("\n========== AI EVALUATION ==========\n")

    try:
        evaluation = json.loads(response)
        print(json.dumps(evaluation, indent=4))

    except json.JSONDecodeError:
        print("The model did not return valid JSON:")
        print(response)


if __name__ == "__main__":
    asyncio.run(main())
