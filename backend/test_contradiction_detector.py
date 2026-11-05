
from app.engine.contradiction_detector import ContradictionDetector


def main():

    detector = ContradictionDetector()

    expected_concepts = [
        "List is mutable",
        "Tuple is immutable",
        "Lists use square brackets",
        "Tuples use parentheses"
    ]

    test_cases = [
        {
            "name": "Correct answer",
            "answer": """
            Lists are mutable and can be modified.
            Tuples are immutable.
            Lists use square brackets.
            Tuples use parentheses.
            """
        },
        {
            "name": "Incorrect answer",
            "answer": """
            Lists are immutable and cannot be modified.
            Tuples are mutable and can be changed.
            Lists use square brackets.
            Tuples use parentheses.
            """
        },
        {
            "name": "Contradictory answer",
            "answer": """
            Lists are mutable and can be modified.
            However, lists are immutable and cannot be changed.
            Tuples are immutable.
            """
        }
    ]

    for test in test_cases:

        result = detector.detect(
            candidate_answer=test["answer"],
            expected_concepts=expected_concepts
        )

        print("\n" + "=" * 55)
        print(test["name"])
        print("=" * 55)

        print("Has contradictions:", result["has_contradictions"])
        print("Detected:", result["contradictions"])


if __name__ == "__main__":
    main()
