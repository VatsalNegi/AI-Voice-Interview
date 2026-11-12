
from app.services.question_quality_validator import (
    QuestionQualityValidator,
)


JD_ANALYSIS = {
    "required_skills": [
        "Python programming",
        "FastAPI",
        "REST API development",
        "PostgreSQL",
        "React",
        "JavaScript",
        "Git",
        "GitHub",
    ],
    "preferred_skills": [
        "Docker",
        "Authentication",
    ],
    "technical_competencies": [
        "Python",
        "FastAPI",
        "REST API",
        "PostgreSQL",
        "React",
        "Git",
        "Docker",
    ],
}


def create_question(
    text,
    competency,
    sequence,
):
    return {
        "question": text,
        "competency": competency,
        "stage": "technical_interview",
        "sequence_number": sequence,
        "expected_concepts": [
            "implementation",
            "best practices",
        ],
    }


def create_questions():
    return [
        create_question(
            "How would you design a FastAPI endpoint "
            "to retrieve job postings from PostgreSQL "
            "with pagination and location filtering?",
            "FastAPI",
            1,
        ),
        create_question(
            "How would you connect a React frontend "
            "to a backend API and handle form submission "
            "and error responses?",
            "React",
            2,
        ),
        create_question(
            "How would you use Docker to containerize "
            "an application and configure communication "
            "between the API and database services?",
            "Docker",
            3,
        ),
        create_question(
            "Explain how Git branches, pull requests "
            "and code reviews help teams manage "
            "software development collaboratively.",
            "Git",
            4,
        ),
    ]


def test_valid_questions():
    questions = create_questions()

    report = QuestionQualityValidator.validate(
        questions,
        JD_ANALYSIS,
    )

    assert report["status"] == "passed"
    assert report["technical_question_count"] == 4
    assert report["distinct_competency_count"] == 4

    print("PASS: Valid technical questions accepted.")


def test_duplicate_questions():
    questions = create_questions()

    questions[1]["question"] = questions[0]["question"]

    try:
        QuestionQualityValidator.validate(
            questions,
            JD_ANALYSIS,
        )

    except ValueError as error:
        print("PASS: Duplicate-like question rejected.")
        print("Reason:", error)
        return

    raise AssertionError(
        "Duplicate questions were not rejected."
    )


def test_low_competency_diversity():
    questions = create_questions()

    questions[0]["competency"] = "FastAPI"
    questions[1]["competency"] = "FastAPI"
    questions[2]["competency"] = "FastAPI"
    questions[3]["competency"] = "FastAPI"

    try:
        QuestionQualityValidator.validate(
            questions,
            JD_ANALYSIS,
        )

    except ValueError as error:
        print("PASS: Low competency diversity rejected.")
        print("Reason:", error)
        return

    raise AssertionError(
        "Low competency diversity was not rejected."
    )


if __name__ == "__main__":
    test_valid_questions()
    test_duplicate_questions()
    test_low_competency_diversity()

    print("\nAll quality validator tests completed.")
