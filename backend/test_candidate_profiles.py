
import asyncio
import uuid

from app.db.models import Candidate, Interview, InterviewQuestion
from app.db.session import get_db_context
from app.services.interview_preparation_service import (
    InterviewPreparationService,
)


PROFILES = [
    {
        "name": "Non-Technical Fresher",
        "resume": """
        Candidate: Rahul Sharma

        Education:
        Bachelor of Commerce, 2025.

        Skills:
        MS Excel, Communication, Problem Solving,
        Basic Computer Knowledge, Basic Python.

        Projects:
        Sales Analysis using Excel.
        Financial Data Management.

        Experience:
        No professional IT experience.
        """,
        "role": "Python Full Stack Developer Intern",
        "jd": """
        Required skills:
        Python, FastAPI or Django, REST API,
        SQL, PostgreSQL, React, JavaScript,
        Git and GitHub.

        Responsibilities:
        Develop backend APIs.
        Integrate frontend and backend.
        Work with databases.
        Debug application functionality.
        """,
    },
    {
        "name": "Technical Fresher",
        "resume": """
        Candidate: Alex Morgan

        Education:
        B.Tech Computer Science.

        Skills:
        Python, JavaScript, React, FastAPI,
        SQL, PostgreSQL, Git, Docker.

        Projects:
        Job Portal using React, FastAPI and PostgreSQL.
        REST API with Authentication.

        Experience:
        No full-time professional experience.
        """,
        "role": "Python Full Stack Developer Intern",
        "jd": """
        Required skills:
        Python, FastAPI, REST APIs, PostgreSQL,
        React, JavaScript, Git, Docker.

        Responsibilities:
        Develop APIs and integrate frontend
        with backend services.
        """,
    },
    {
        "name": "Python Developer - 3 Years",
        "resume": """
        Candidate: Amit Kumar

        Education:
        B.Tech Computer Science.

        Experience:
        3 years as Python Developer.

        Skills:
        Python, FastAPI, Django, PostgreSQL,
        React, Docker, AWS, Git, REST APIs.

        Work:
        Developed scalable REST APIs.
        Optimized database queries.
        Implemented JWT authentication.
        Integrated React frontend.
        Deployed applications using Docker and AWS.

        Projects:
        E-commerce Platform.
        Employee Management System.
        """,
        "role": "Python Full Stack Developer",
        "jd": """
        Required:
        Advanced Python, FastAPI, PostgreSQL,
        React, Docker, AWS, Microservices,
        System Design and CI/CD.

        Responsibilities:
        Design scalable applications.
        Optimize application performance.
        Review code.
        Lead technical implementation.
        """,
    },
    {
        "name": "Senior Developer - 8 Years",
        "resume": """
        Candidate: Priya Sharma

        Education:
        B.Tech Computer Science.

        Experience:
        8 years in software development.

        Skills:
        Python, Java, FastAPI, Django,
        React, PostgreSQL, Redis, Docker,
        Kubernetes, AWS, Microservices,
        CI/CD, System Design.

        Work:
        Designed distributed backend systems.
        Led a team of 8 developers.
        Improved API performance.
        Designed microservice architecture.
        Managed cloud infrastructure.
        Conducted code reviews and mentoring.

        Projects:
        Enterprise Banking Platform.
        Distributed E-commerce System.
        """,
        "role": "Senior Software Architect",
        "jd": """
        Required:
        System Design, Python, Microservices,
        Distributed Systems, AWS, Kubernetes,
        PostgreSQL, Redis, CI/CD.

        Responsibilities:
        Design enterprise architecture.
        Lead engineering teams.
        Make technical decisions.
        Improve system scalability and reliability.
        """,
    },
    {
        "name": "Candidate Without Resume",
        "resume": "",
        "role": "Python Developer Intern",
        "jd": """
        Required:
        Python, FastAPI, SQL, REST APIs,
        JavaScript, React, Git.

        Responsibilities:
        Develop APIs.
        Work with databases.
        Debug applications.
        Collaborate with developers.
        """,
    },
]


def create_records(profile):
    session_id = f"profile-test-{uuid.uuid4().hex[:12]}"
    candidate_id = f"candidate-test-{uuid.uuid4().hex[:12]}"

    with get_db_context() as db:
        candidate = Candidate(
            candidate_id=candidate_id,
            candidate_name=profile["name"],
            email=f"{candidate_id}@example.test",
            resume_text=profile["resume"],
        )

        db.add(candidate)
        db.flush()

        interview = Interview(
            session_id=session_id,
            candidate_id=candidate.id,
            job_role=profile["role"],
            job_description=profile["jd"],
            interview_duration=30,
            language="English",
            status="not_started",
            current_stage="preparation",
            preparation_status="pending",
            total_questions=0,
        )

        db.add(interview)

    return session_id, candidate_id


def verify_results(session_id):
    with get_db_context() as db:
        interview = (
            db.query(Interview)
            .filter(Interview.session_id == session_id)
            .first()
        )

        if interview is None:
            raise AssertionError("Interview record not found.")

        questions = (
            db.query(InterviewQuestion)
            .filter(
                InterviewQuestion.interview_id == interview.id,
                InterviewQuestion.question_type == "primary",
            )
            .order_by(InterviewQuestion.sequence_number)
            .all()
        )

        metadata = interview.blueprint_metadata or {}
        resume_analysis = metadata.get("resume_analysis", {})

        print("\nPreparation status:", interview.preparation_status)
        print("Preparation error:", interview.preparation_error)
        print("Candidate classification:",
              resume_analysis.get("candidate_type"))
        print("Classification confidence:",
              resume_analysis.get("classification_confidence"))
        print("Question count:", len(questions))

        print("\nGenerated questions:")

        for q in questions:
            snapshot = q.metadata_snapshot or {}
            print(
                f"{q.sequence_number}. "
                f"[{snapshot.get('stage', 'unknown')}] "
                f"{q.question_text}"
            )

        assert interview.preparation_status == "ready", (
            f"Preparation failed: {interview.preparation_error}"
        )

        assert len(questions) == 10
        assert interview.total_questions == 10

        return {
            "status": interview.preparation_status,
            "candidate_type": resume_analysis.get("candidate_type"),
            "question_count": len(questions),
        }


def cleanup(candidate_id):
    with get_db_context() as db:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.candidate_id == candidate_id)
            .first()
        )

        if candidate:
            db.delete(candidate)


async def run_profile(profile):
    print("\n" + "=" * 75)
    print("PROFILE:", profile["name"])
    print("=" * 75)

    session_id, candidate_id = create_records(profile)

    try:
        print("\nRunning interview preparation...")

        await InterviewPreparationService.run(session_id)

        result = verify_results(session_id)

        print("\nPROFILE TEST PASSED:", profile["name"])
        return result

    except Exception as exc:
        print("\nPROFILE TEST FAILED:", profile["name"])
        print("Error:", repr(exc))
        return {"status": "failed", "error": str(exc)}

    finally:
        cleanup(candidate_id)
        print("Test records cleaned up.")


async def main():
    results = []

    for profile in PROFILES:
        result = await run_profile(profile)
        results.append({
            "profile": profile["name"],
            **result,
        })

    print("\n" + "=" * 75)
    print("CROSS-PROFILE TEST SUMMARY")
    print("=" * 75)

    for result in results:
        print(
            result["profile"],
            "| Status:", result["status"],
            "| Type:", result.get("candidate_type", "N/A"),
            "| Questions:", result.get("question_count", 0),
        )

    passed = sum(r["status"] == "ready" for r in results)

    print(f"\nFINAL RESULT: {passed}/{len(results)} profiles prepared successfully.")


if __name__ == "__main__":
    asyncio.run(main())
