
import asyncio
import uuid
from datetime import datetime, timezone

from app.db.models import Candidate, Interview, InterviewQuestion
from app.db.session import get_db_context
from app.services.interview_preparation_service import (
    InterviewPreparationService,
)


SESSION_ID = f"gemini-integration-{uuid.uuid4().hex[:12]}"
CANDIDATE_ID = f"gemini-test-{uuid.uuid4().hex[:12]}"

RESUME = """
Candidate: Alex Morgan

Education:
Bachelor of Technology in Computer Science.

Technical Skills:
Python, JavaScript, React, FastAPI, SQL, PostgreSQL,
REST APIs, Git, Docker.

Academic Projects:
1. Developed a job portal using React, FastAPI and PostgreSQL.
2. Built a machine learning model for student performance prediction.
3. Created REST APIs with authentication and database integration.

Experience:
No full-time professional employment experience.
"""

JOB_ROLE = "Python Full Stack Developer Intern"

JOB_DESCRIPTION = """
We are looking for a Python Full Stack Developer Intern.

Required technical skills:
- Python programming
- FastAPI or Django
- REST API development
- SQL and PostgreSQL
- React and JavaScript
- Git and GitHub

Responsibilities:
- Develop and maintain backend APIs.
- Integrate frontend applications with backend services.
- Work with relational databases.
- Debug and test application functionality.
- Collaborate with the development team.

Preferred:
- Docker fundamentals
- Basic understanding of authentication
- Knowledge of software development lifecycle
"""


def create_test_records():
    with get_db_context() as db:
        candidate = Candidate(
            candidate_id=CANDIDATE_ID,
            candidate_name="Gemini Integration Test Candidate",
            email=f"{CANDIDATE_ID}@example.test",
            resume_text=RESUME,
        )

        db.add(candidate)
        db.flush()

        interview = Interview(
            session_id=SESSION_ID,
            candidate_id=candidate.id,
            job_role=JOB_ROLE,
            job_description=JOB_DESCRIPTION,
            interview_duration=30,
            language="English",
            status="not_started",
            current_stage="preparation",
            preparation_status="pending",
            total_questions=0,
        )

        db.add(interview)

    print("Test candidate and interview created.")
    print("Session ID:", SESSION_ID)


def verify_results():
    with get_db_context() as db:
        interview = (
            db.query(Interview)
            .filter(Interview.session_id == SESSION_ID)
            .first()
        )

        if interview is None:
            raise AssertionError("Test interview was not found.")

        questions = (
            db.query(InterviewQuestion)
            .filter(
                InterviewQuestion.interview_id == interview.id,
                InterviewQuestion.question_type == "primary",
            )
            .order_by(InterviewQuestion.sequence_number)
            .all()
        )

        print("\n========== PREPARATION RESULTS ==========")
        print("Preparation status:", interview.preparation_status)
        print("Preparation error:", interview.preparation_error)
        print("Total questions:", interview.total_questions)
        print("Saved primary questions:", len(questions))

        metadata = interview.blueprint_metadata or {}
        print("Blueprint metadata:", metadata)

        print("\nGenerated questions:")

        for question in questions:
            snapshot = question.metadata_snapshot or {}

            print(
                f"{question.sequence_number}. "
                f"[{snapshot.get('stage', 'unknown')}] "
                f"{question.question_text}"
            )

        assert interview.preparation_status == "ready", (
            f"Preparation failed: {interview.preparation_error}"
        )

        assert interview.total_questions == 10
        assert len(questions) == 10

        assert [
            q.sequence_number for q in questions
        ] == list(range(1, 11))

        print("\nSUCCESS: Gemini preparation passed all checks.")


def cleanup():
    with get_db_context() as db:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.candidate_id == CANDIDATE_ID)
            .first()
        )

        if candidate is not None:
            db.delete(candidate)

    print("Test candidate and associated records cleaned up.")


async def main():
    created = False

    try:
        create_test_records()
        created = True

        print("\nRunning actual interview preparation pipeline...")
        await InterviewPreparationService.run(SESSION_ID)

        verify_results()

    finally:
        if created:
            cleanup()


if __name__ == "__main__":
    asyncio.run(main())
