from app.services.semantic_evaluator import SemanticEvaluator

def main():

    evaluator = SemanticEvaluator()

    answer = """
    We can modify list elements after creation.
    A tuple is fixed and its elements cannot be reassigned.
    Lists use square brackets.
    """

    expected_concepts = [
        "List is mutable",
        "Tuple is immutable",
        "Lists use square brackets",
        "Tuples use parentheses"
    ]

    result = evaluator.evaluate_concepts(
        candidate_answer=answer,
        expected_concepts=expected_concepts
    )

    print("\n========== SEMANTIC EVALUATION ==========\n")

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()