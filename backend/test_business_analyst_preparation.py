
import asyncio
import uuid

from app.db.models import Candidate, Interview, InterviewQuestion
from app.db.session import get_db_context
from app.services.interview_preparation_service import (
    InterviewPreparationService,
)


SESSION_ID = f"ba-integration-{uuid.uuid4().hex[:12]}"
CANDIDATE_ID = f"ba-test-{uuid.uuid4().hex[:12]}"


# --------------------------------------------------
# TEST CANDIDATE RESUME
# --------------------------------------------------

RESUME = """
Candidate: Alex Morgan

Education:
Bachelor's degree in Business Administration.

Technical Skills:
Microsoft Excel, SQL, Power BI, Data Analysis,
Reporting, Dashboard Creation, Documentation.

Academic Projects:

1. Sales Performance Analysis:
   Analyzed sales data using Excel and SQL.
   Created reports and dashboards to identify
   business trends and performance indicators.

2. Business Process Improvement:
   Studied an academic business workflow and
   documented process requirements and improvements.

3. Student Performance Dashboard:
   Created a dashboard to present performance
   metrics and support data-driven decisions.

Experience:
No full-time professional employment experience.
"""


# --------------------------------------------------
# BUSINESS ANALYST JOB DESCRIPTION
# --------------------------------------------------

JOB_ROLE = "Business Analyst"

JOB_DESCRIPTION = """
Job Title: Business Analyst

Experience: 0-2 years

Employment Type: Full-time

Overview:
We are looking for a detail-oriented Business Analyst
to understand business requirements, analyze data,
and support decision-making through actionable insights.

Responsibilities:

- Gather and document business requirements from stakeholders.
- Analyze business processes and identify areas for improvement.
- Prepare reports, dashboards, and presentations.
- Work with Excel and SQL to analyze business data.
- Coordinate with technical and business teams.
- Translate business requirements into functional specifications.
"""


# --------------------------------------------------
# CREATE TEST RECORDS
# --------------------------------------------------

def create_test_records():

    with get_db_context() as db:

        candidate = Candidate(
            candidate_id=CANDIDATE_ID,
            candidate_name="Business Analyst Test Candidate",
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

    print("Business Analyst test candidate and interview created.")
    print("Session ID:", SESSION_ID)


# --------------------------------------------------
# VERIFY PREPARATION RESULTS
# --------------------------------------------------

def verify_results():

    with get_db_context() as db:

        interview = (
            db.query(Interview)
            .filter(Interview.session_id == SESSION_ID)
            .first()
        )

        if interview is None:
            raise AssertionError(
                "Business Analyst test interview was not found."
            )

        questions = (
            db.query(InterviewQuestion)
            .filter(
                InterviewQuestion.interview_id == interview.id,
                InterviewQuestion.question_type == "primary",
            )
            .order_by(InterviewQuestion.sequence_number)
            .all()
        )

        print("\n========== BUSINESS ANALYST RESULTS ==========")

        print("Preparation status:", interview.preparation_status)
        print("Preparation error:", interview.preparation_error)
        print("Total questions:", interview.total_questions)
        print("Saved primary questions:", len(questions))

        metadata = interview.blueprint_metadata or {}

        print("\nQuestion quality report:")

        quality_report = metadata.get(
            "question_quality_report",
            {},
        )

        print(quality_report)

        print("\nGenerated questions:")

        technical_competencies = []

        for question in questions:

            snapshot = question.metadata_snapshot or {}

            stage = snapshot.get("stage", "unknown")

            # Competency is stored in the database column.
            # The metadata snapshot uses the key jd_competency.
            competency = (
                question.competency
                or snapshot.get("jd_competency", "")
            )

            print(
                f"\n{question.sequence_number}. [{stage}] "
                f"{question.question_text}"
            )

            if stage == "technical_interview":

                print("   Competency:", competency)

                technical_competencies.append(competency)

        # ------------------------------------------
        # BASIC PREPARATION ASSERTIONS
        # ------------------------------------------

        assert interview.preparation_status == "ready", (
            f"Preparation failed: {interview.preparation_error}"
        )

        assert interview.total_questions == 10

        assert len(questions) == 10

        assert [
            q.sequence_number for q in questions
        ] == list(range(1, 11))

        # ------------------------------------------
        # TECHNICAL QUESTION ASSERTIONS
        # ------------------------------------------

        assert len(technical_competencies) == 4, (
            f"Expected 4 technical questions, "
            f"received {len(technical_competencies)}"
        )

        assert all(
            isinstance(value, str) and value.strip()
            for value in technical_competencies
        ), "One or more technical questions have no competency."

        assert len({
            competency.casefold().strip()
            for competency in technical_competencies
        }) >= 3, (
            "Technical questions do not cover enough distinct competencies."
        )

        # ------------------------------------------
        # ORIGINAL BUSINESS ANALYST REGRESSION
        # ------------------------------------------

        forbidden_competency = "data cleaning and validation"

        assert all(
            competency.casefold().strip() != forbidden_competency
            for competency in technical_competencies
        ), (
            "Regression detected: unsupported competency "
            "'Data Cleaning and Validation' was generated."
        )

        # ------------------------------------------
        # QUALITY REPORT ASSERTIONS
        # ------------------------------------------

        assert quality_report.get("status") == "passed", (
            "Question quality validation did not pass."
        )

        assert quality_report.get(
            "technical_question_count"
        ) == 4

        assert quality_report.get(
            "distinct_competency_count", 0
        ) >= 3

        print("\n==============================================")
        print("SUCCESS: Business Analyst preparation passed.")
        print("Total questions: 10")
        print("Technical questions: 4")
        print(
            "Distinct competencies:",
            quality_report.get("distinct_competency_count"),
        )
        print("Unsupported competency regression: Not detected")
        print("==============================================")


# --------------------------------------------------
# CLEANUP
# --------------------------------------------------

def cleanup():

    with get_db_context() as db:

        candidate = (
            db.query(Candidate)
            .filter(Candidate.candidate_id == CANDIDATE_ID)
            .first()
        )

        if candidate is not None:
            db.delete(candidate)

    print("\nBusiness Analyst test records cleaned up.")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

async def main():

    created = False

    try:

        create_test_records()
        created = True

        print("\nRunning Business Analyst preparation pipeline...")

        await InterviewPreparationService.run(SESSION_ID)

        verify_results()

    finally:

        if created:
            cleanup()


if __name__ == "__main__":
    asyncio.run(main())
