
from app.services.interview_preparation_service import (
    InterviewPreparationService
)

clean = InterviewPreparationService._clean_generated_text

test_cases = [
    (
        "How would you fetch job listings,ensuring efficient data flow?",
        "How would you fetch job listings, ensuring efficient data flow?",
    ),
    (
        "What role did you play,and what was the outcome?",
        "What role did you play, and what was the outcome?",
    ),
    (
        "Describe your experience with React and FastAPI.",
        "Describe your experience with React and FastAPI.",
    ),
    (
        "  Explain   your   approach   to debugging.  ",
        "Explain your approach to debugging.",
    ),
]

for original, expected in test_cases:
    result = clean(original)

    print("Original:", original)
    print("Cleaned: ", result)

    assert result == expected, (
        f"Expected: {expected!r}, got: {result!r}"
    )

print("\nSUCCESS: All normalization tests passed.")
