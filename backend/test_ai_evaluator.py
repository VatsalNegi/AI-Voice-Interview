
import asyncio
from app.services.ai_evaluator import AIEvaluator

QUESTION = "What is the difference between a Python list and tuple?"

EXPECTED_CONCEPTS = [
    "List is mutable",
    "Tuple is immutable",
    "Lists use square brackets",
    "Tuples use parentheses"
]

SCENARIOS = {
    "CORRECT ANSWER": """
        Lists are mutable, so we can modify them.
        Tuples are immutable, so their elements cannot be reassigned.
        Lists use square brackets and tuples use parentheses.
    """,

    "INCORRECT ANSWER": """
        Lists are immutable, while tuples are mutable.
        Lists use parentheses and tuples use square brackets.
    """,

    "INCOMPLETE ANSWER": """
        Lists are mutable, so we can modify them.
    """,

    "PARAPHRASED ANSWER": """
        A list can be modified after it is created,
        but a tuple cannot be changed after creation.
        Lists are written using square brackets,
        whereas tuples use parentheses.
    """
}


async def main():
    evaluator = AIEvaluator()

    for scenario, answer in SCENARIOS.items():
        print("\n" + "=" * 65)
        print(f"SCENARIO: {scenario}")
        print("=" * 65)

        try:
            result = await evaluator.evaluate_answer(
                question=QUESTION,
                expected_concepts=EXPECTED_CONCEPTS,
                candidate_answer=answer
            )

            print(result.model_dump_json(indent=4))

        except Exception as error:
            print(f"Evaluation failed: {error}")


if __name__ == "__main__":
    asyncio.run(main())
