
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from fastapi.testclient import TestClient

from app.db.session import engine, get_db_context, Base
from app.db.models import (
    Recruiter,
    Candidate,
    Interview,
    InterviewQuestion,
    CandidateAnswer,
    Evaluation,
)
from app.schemas.interview import InterviewSessionCreate, CandidateContext
from app.services.session_manager import SessionManager, active_sessions
from app.services.interview_preparation_service import InterviewPreparationService
from app.services.jd_question_generator import JDQuestionGenerator
from app.auth.security import create_access_token
from app.main import app


# ============================================================
# DATABASE FIXTURE
# ============================================================

@pytest.fixture(autouse=True)
def ensure_tables():
    """Ensure database tables exist before each test."""
    Base.metadata.create_all(bind=engine)
    yield


# ============================================================
# DETERMINISTIC QUESTION PREPARATION
# ============================================================

def prepare_test_interview(session_id: str, candidate_type: str = "fresher"):
    """
    Prepare an interview using deterministic questions.

    This deliberately avoids Gemini, OpenRouter, and network calls.
    It writes the same database state expected from successful
    production preparation.
    """

    if candidate_type not in {"fresher", "experienced", "uncertain"}:
        raise ValueError("Invalid candidate type for test preparation.")

    stages = (
        ["introduction"]
        + ["candidate_background"] * 2
        + ["technical_interview"] * 4
        + ["behavioral_interview"] * 2
        + ["closing"]
    )

    stage_labels = JDQuestionGenerator.STAGES
    now = datetime.now(timezone.utc)

    with get_db_context() as db:
        interview = (
            db.query(Interview)
            .filter(Interview.session_id == session_id)
            .first()
        )

        if interview is None:
            raise ValueError(f"Interview not found: {session_id}")

        # Preparation must only happen before interview start.
        if interview.status != "not_started":
            raise ValueError("Cannot prepare an already-started interview.")

        # Avoid inserting duplicate questions.
        existing = (
            db.query(InterviewQuestion)
            .filter(InterviewQuestion.interview_id == interview.id)
            .count()
        )

        if existing:
            db.query(InterviewQuestion).filter(
                InterviewQuestion.interview_id == interview.id
            ).delete(synchronize_session=False)

        for index, stage in enumerate(stages, start=1):
            branch = (
                candidate_type
                if stage == "candidate_background"
                else "all"
            )

            competency = (
                "Python development"
                if stage == "technical_interview"
                else "General interview competency"
            )

            question = InterviewQuestion(
                interview_id=interview.id,
                question_id=str(uuid4()),
                question_text=(
                    f"Test interview question {index}: "
                    f"Please explain your approach and reasoning."
                ),
                competency=competency,
                difficulty="medium",
                question_type="primary",
                sequence_number=index,
                expected_concepts=[
                    f"concept_{index}_one",
                    f"concept_{index}_two",
                ],
                estimated_time_seconds=90,
                asked_at=None,
                metadata_snapshot={
                    "source": "deterministic_test_fixture",
                    "generation_strategy": "pre_generated_staged_branching",
                    "stage": stage,
                    "stage_label": stage_labels[stage],
                    "candidate_branch": branch,
                    "jd_competency": competency,
                },
            )

            db.add(question)

        interview.total_questions = 10
        interview.preparation_status = "ready"
        interview.preparation_error = None
        interview.prepared_at = now

        interview.blueprint_metadata = {
            "candidate_type": candidate_type,
            "classification_confidence": "high",
            "question_count": 10,
            "stage_sequence": stages,
            "generation_source": "deterministic_test_fixture",
            "question_generation_strategy": (
                "pre_generated_staged_branching"
            ),
            "live_llm_question_generation": False,
            "prepared_at": now.isoformat(),
        }

        db.flush()

    # Refresh the runtime cache from persistent database state.
    SessionManager.get_session(session_id)


async def mock_background_preparation(session_id: str):
    """Async replacement for the API background preparation task."""
    prepare_test_interview(session_id)


# ============================================================
# TEST 1: DATABASE CONNECTION
# ============================================================

def test_1_database_connection_and_tables():
    """Verify database connection and all required tables."""

    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    required_tables = [
        "recruiters",
        "candidates",
        "interviews",
        "interview_questions",
        "candidate_answers",
        "evaluations",
    ]

    for table in required_tables:
        assert table in table_names, f"Table {table} missing."


# ============================================================
# TEST 2: RECRUITER MODEL
# ============================================================

def test_2_recruiter_model_and_constraints():
    """Verify recruiter persistence and email uniqueness."""

    unique_email = f"recruiter_{os.urandom(4).hex()}@example.com"

    with get_db_context() as db:
        recruiter = Recruiter(
            full_name="Jane HR",
            email=unique_email,
            password_hash="argon2_hash_placeholder",
            is_active=True,
        )
        db.add(recruiter)

    try:
        with get_db_context() as db:
            saved = (
                db.query(Recruiter)
                .filter(Recruiter.email == unique_email)
                .first()
            )

            assert saved is not None
            assert saved.full_name == "Jane HR"
            assert saved.is_active is True
            assert saved.created_at is not None
            assert saved.updated_at is not None

    finally:
        with get_db_context() as db:
            saved = (
                db.query(Recruiter)
                .filter(Recruiter.email == unique_email)
                .first()
            )
            if saved:
                db.delete(saved)


# ============================================================
# TEST 3: INTERVIEW CREATION
# ============================================================

def test_3_interview_creation():
    """Verify interview creation and pending preparation state."""

    candidate_id = f"cand_{os.urandom(4).hex()}"

    payload = InterviewSessionCreate(
        candidate=CandidateContext(
            candidate_id=candidate_id,
            candidate_name="Alice Candidate",
            email="alice@example.com",
            resume_text="Experienced Python and FastAPI backend developer.",
            job_role="Senior Backend Engineer",
            job_description="Build scalable microservices and APIs.",
        ),
        interview_duration=45,
        language="English",
    )

    session = SessionManager.create_session(payload)
    session_id = session["session_id"]

    assert session_id is not None
    assert session["status"] == "not_started"
    assert session["current_stage"] == "preparation"
    assert session["preparation_status"] == "pending"
    assert session["total_questions"] == 0

    with get_db_context() as db:
        db_interview = (
            db.query(Interview)
            .filter(Interview.session_id == session_id)
            .first()
        )

        assert db_interview is not None
        assert db_interview.job_role == "Senior Backend Engineer"
        assert db_interview.interview_duration == 45
        assert db_interview.status == "not_started"
        assert db_interview.preparation_status == "pending"

        db_candidate = (
            db.query(Candidate)
            .filter(Candidate.candidate_id == candidate_id)
            .first()
        )

        assert db_candidate is not None
        assert db_candidate.candidate_name == "Alice Candidate"
        assert db_interview.candidate_id == db_candidate.id

    SessionManager.delete_interview(session_id)


# ============================================================
# TEST 4: INTERVIEW START
# ============================================================

def test_4_interview_start():
    """Verify prepared interview starts with the first saved question."""

    candidate_id = f"cand_{os.urandom(4).hex()}"

    payload = InterviewSessionCreate(
        candidate=CandidateContext(
            candidate_id=candidate_id,
            candidate_name="Bob Developer",
            email="bob@example.com",
            resume_text="Python and backend systems.",
            job_role="Python Engineer",
            job_description="Backend developer.",
        ),
        interview_duration=30,
        language="English",
    )

    session = SessionManager.create_session(payload)
    session_id = session["session_id"]

    try:
        # The interview cannot start before preparation.
        with pytest.raises(ValueError, match="still being prepared"):
            SessionManager.start_session(session_id)

        prepare_test_interview(session_id, "fresher")

        started = SessionManager.start_session(session_id)

        assert started["status"] == "in_progress"
        assert started["current_question"] is not None
        assert started["preparation_status"] == "ready"

        first_q_id = started["current_question"]["question_id"]

        with get_db_context() as db:
            db_interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .first()
            )

            assert db_interview.status == "in_progress"
            assert db_interview.start_time is not None
            assert db_interview.current_question_id == first_q_id

            stored_questions = (
                db.query(InterviewQuestion)
                .filter(
                    InterviewQuestion.interview_id == db_interview.id
                )
                .order_by(InterviewQuestion.sequence_number.asc())
                .all()
            )

            assert len(stored_questions) == 10
            assert stored_questions[0].question_id == first_q_id
            assert stored_questions[0].question_type == "primary"
            assert stored_questions[0].sequence_number == 1
            assert stored_questions[0].asked_at is not None

    finally:
        SessionManager.delete_interview(session_id)


# ============================================================
# TEST 5: ANSWER PERSISTENCE AND QUESTION PROGRESSION
# ============================================================

@pytest.mark.asyncio
async def test_5_initial_and_followup_answer_persistence():
    """
    Verify answer persistence and progression to the next
    pre-generated question.

    The current SessionManager implementation saves answers and
    advances questions. Final evaluation is handled separately.
    """

    candidate_id = f"cand_{os.urandom(4).hex()}"

    payload = InterviewSessionCreate(
        candidate=CandidateContext(
            candidate_id=candidate_id,
            candidate_name="Charlie Test",
            email="charlie@example.com",
            resume_text="Software engineer with Python experience.",
            job_role="Software Engineer",
            job_description="General software engineering.",
        ),
        interview_duration=30,
        language="English",
    )

    session = SessionManager.create_session(payload)
    session_id = session["session_id"]

    try:
        prepare_test_interview(session_id, "experienced")
        started = SessionManager.start_session(session_id)

        first_question_id = started["current_question"]["question_id"]

        result_first = await SessionManager.submit_answer(
            session_id=session_id,
            answer_text="I graduated in computer science.",
        )

        assert result_first["next_action"] == "NEXT_QUESTION"
        assert result_first["next_question"] is not None
        assert (
            result_first["next_question"]["question_id"]
            != first_question_id
        )

        with get_db_context() as db:
            db_interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .first()
            )

            assert db_interview.current_question_id == (
                result_first["next_question"]["question_id"]
            )

            answers = (
                db.query(CandidateAnswer)
                .join(InterviewQuestion)
                .filter(
                    InterviewQuestion.interview_id == db_interview.id
                )
                .all()
            )

            assert len(answers) == 1
            assert answers[0].answer_type == "initial"
            assert answers[0].answer_text == (
                "I graduated in computer science."
            )

        result_second = await SessionManager.submit_answer(
            session_id=session_id,
            answer_text=(
                "I primarily use Python, FastAPI, and PostgreSQL "
                "for my projects."
            ),
        )

        assert result_second["next_action"] == "NEXT_QUESTION"

        with get_db_context() as db:
            db_interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .first()
            )

            answers = (
                db.query(CandidateAnswer)
                .join(InterviewQuestion)
                .filter(
                    InterviewQuestion.interview_id == db_interview.id
                )
                .order_by(CandidateAnswer.created_at.asc())
                .all()
            )

            assert len(answers) == 2
            assert answers[0].answer_text == (
                "I graduated in computer science."
            )
            assert answers[1].answer_text == (
                "I primarily use Python, FastAPI, and PostgreSQL "
                "for my projects."
            )

            assert all(
                answer.answer_type == "initial"
                for answer in answers
            )

            # Evaluation is not performed by the current submit_answer().
            assert (
                db.query(Evaluation)
                .filter(Evaluation.interview_id == db_interview.id)
                .count()
                == 0
            )

    finally:
        SessionManager.delete_interview(session_id)


# ============================================================
# TEST 6: RESTART SIMULATION AND HISTORY
# ============================================================

def test_6_restart_simulation_and_history_retrieval():
    """Verify persisted session recovery after clearing memory cache."""

    candidate_id = f"cand_{os.urandom(4).hex()}"

    payload = InterviewSessionCreate(
        candidate=CandidateContext(
            candidate_id=candidate_id,
            candidate_name="Restart Candidate",
            email="restart@example.com",
            resume_text="Python engineer.",
            job_role="Backend Developer",
            job_description="APIs",
        ),
        interview_duration=30,
        language="English",
    )

    session = SessionManager.create_session(payload)
    session_id = session["session_id"]

    try:
        prepare_test_interview(session_id, "uncertain")
        SessionManager.start_session(session_id)

        active_sessions.clear()
        assert len(active_sessions) == 0

        recovered = SessionManager.get_session(session_id)

        assert recovered is not None
        assert recovered["session_id"] == session_id
        assert recovered["status"] == "in_progress"
        assert recovered["candidate"]["candidate_name"] == (
            "Restart Candidate"
        )
        assert recovered["current_question"] is not None
        assert len(recovered["asked_question_ids"]) == 1
        assert len(recovered["transcript"]) >= 1

        history = SessionManager.get_all_interviews()

        matching = [
            item for item in history
            if item["session_id"] == session_id
        ]

        assert len(matching) == 1
        assert matching[0]["candidate_name"] == "Restart Candidate"
        assert matching[0]["status"] == "in_progress"

    finally:
        SessionManager.delete_interview(session_id)


# ============================================================
# TEST 7: CASCADE DELETION
# ============================================================

def test_7_cascade_deletion():
    """Verify associated questions, answers, and evaluations are deleted."""

    candidate_id = f"cand_{os.urandom(4).hex()}"

    payload = InterviewSessionCreate(
        candidate=CandidateContext(
            candidate_id=candidate_id,
            candidate_name="Cascade Test",
            email="cascade@example.com",
            resume_text="Tester.",
            job_role="QA",
            job_description="Testing",
        ),
        interview_duration=30,
        language="English",
    )

    session = SessionManager.create_session(payload)
    session_id = session["session_id"]

    prepare_test_interview(session_id, "uncertain")
    SessionManager.start_session(session_id)

    with get_db_context() as db:
        interview = (
            db.query(Interview)
            .filter(Interview.session_id == session_id)
            .first()
        )

        interview_id = interview.id

        question = (
            db.query(InterviewQuestion)
            .filter(
                InterviewQuestion.interview_id == interview_id
            )
            .first()
        )

        answer = CandidateAnswer(
            question_id=question.id,
            answer_text="Testing answers",
            answer_type="initial",
        )

        db.add(answer)

        evaluation = Evaluation(
            interview_id=interview_id,
            question_id=question.id,
            answer_classification="GOOD",
        )

        db.add(evaluation)

    deleted = SessionManager.delete_interview(session_id)
    assert deleted is True

    with get_db_context() as db:
        assert (
            db.query(Interview)
            .filter(Interview.id == interview_id)
            .first()
            is None
        )

        assert (
            db.query(InterviewQuestion)
            .filter(
                InterviewQuestion.interview_id == interview_id
            )
            .count()
            == 0
        )

        assert (
            db.query(CandidateAnswer)
            .join(InterviewQuestion)
            .filter(
                InterviewQuestion.interview_id == interview_id
            )
            .count()
            == 0
        )

        assert (
            db.query(Evaluation)
            .filter(Evaluation.interview_id == interview_id)
            .count()
            == 0
        )


# ============================================================
# TEST 8: FASTAPI ENDPOINTS AND AUTHENTICATION
# ============================================================

def test_8_fastapi_endpoints(monkeypatch):
    """Test API routes, background preparation, and recruiter auth."""

    client = TestClient(app)

    # Replace only the background preparation task.
    # Production preparation logic remains unchanged.
    monkeypatch.setattr(
        InterviewPreparationService,
        "run",
        staticmethod(mock_background_preparation),
    )

    unique_email = f"api_recruiter_{os.urandom(4).hex()}@example.com"

    with get_db_context() as db:
        recruiter = Recruiter(
            full_name="API Test Recruiter",
            email=unique_email,
            password_hash="test_password_hash",
            is_active=True,
        )
        db.add(recruiter)
        db.flush()
        recruiter_id = recruiter.id

    token = create_access_token(recruiter_id)
    headers = {"Authorization": f"Bearer {token}"}

    session_id = None

    try:
        # 1. Health check
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["database"] == "connected"

        # 2. Create interview
        create_payload = {
            "candidate": {
                "candidate_id": f"cand_{os.urandom(4).hex()}",
                "candidate_name": "API Candidate",
                "email": "api@example.com",
                "resume_text": "Full stack engineer",
                "job_role": "Full Stack Engineer",
                "job_description": "React and FastAPI",
            },
            "interview_duration": 40,
            "language": "English",
        }

        response = client.post(
            "/interviews/create",
            json=create_payload,
        )

        assert response.status_code == 200

        data = response.json()
        session_id = data["session_id"]

        assert data["candidate_name"] == "API Candidate"

        # 3. Retrieve candidate interview
        response = client.get(f"/interviews/{session_id}")

        assert response.status_code == 200
        assert response.json()["session_id"] == session_id

        # 4. Start interview after deterministic preparation
        response = client.post(
            f"/interviews/{session_id}/start"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "in_progress"

        # 5. Protected history endpoint
        response = client.get(
            "/interviews",
            headers=headers,
        )

        assert response.status_code == 200

        interviews = response.json()["interviews"]

        assert any(
            item["session_id"] == session_id
            for item in interviews
        )

        # 6. Protected delete endpoint
        response = client.delete(
            f"/interviews/{session_id}",
            headers=headers,
        )

        assert response.status_code == 200
        assert response.json()["session_id"] == session_id

        # 7. Confirm deleted session returns 404
        response = client.get(f"/interviews/{session_id}")

        assert response.status_code == 404

        session_id = None

    finally:
        if session_id:
            SessionManager.delete_interview(session_id)

        with get_db_context() as db:
            recruiter = (
                db.query(Recruiter)
                .filter(Recruiter.email == unique_email)
                .first()
            )

            if recruiter:
                db.delete(recruiter)
