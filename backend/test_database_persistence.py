import os
import sys
from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, patch

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
from app.schemas.ai_evaluation import AIEvaluation
from app.services.session_manager import SessionManager, active_sessions
from app.main import app


@pytest.fixture(autouse=True)
def ensure_tables():
    """Ensure database schema tables are created before running tests."""
    Base.metadata.create_all(bind=engine)
    yield


def test_1_database_connection_and_tables():
    """Verify database connection and all 6 normalized tables exist."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    required_tables = [
        "recruiters",
        "candidates",
        "interviews",
        "interview_questions",
        "candidate_answers",
        "evaluations"
    ]

    for table in required_tables:
        assert table in table_names, f"Table {table} missing from database."


def test_2_recruiter_model_and_constraints():
    """Verify Recruiter model persistence, constraints, and email uniqueness."""
    unique_email = f"recruiter_{os.urandom(4).hex()}@example.com"
    with get_db_context() as db:
        recruiter = Recruiter(
            full_name="Jane HR",
            email=unique_email,
            password_hash="argon2_hash_placeholder",
            is_active=True
        )
        db.add(recruiter)

    with get_db_context() as db:
        saved = db.query(Recruiter).filter(Recruiter.email == unique_email).first()
        assert saved is not None
        assert saved.full_name == "Jane HR"
        assert saved.is_active is True
        assert saved.created_at is not None
        assert saved.updated_at is not None

        # Clean up
        db.delete(saved)


def test_3_interview_creation():
    """Test creating an interview session and verifying persistent candidate and interview records."""
    candidate_id = f"cand_{os.urandom(4).hex()}"
    payload = InterviewSessionCreate(
        candidate=CandidateContext(
            candidate_id=candidate_id,
            candidate_name="Alice Candidate",
            email="alice@example.com",
            resume_text="Experienced Python and FastAPI backend developer.",
            job_role="Senior Backend Engineer",
            job_description="Build scalable microservices and APIs."
        ),
        interview_duration=45,
        language="English"
    )

    session = SessionManager.create_session(payload)
    session_id = session["session_id"]

    assert session_id is not None
    assert session["status"] == "not_started"
    assert session["current_stage"] == "introduction"

    # Verify directly in persistent database
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

        db_candidate = (
            db.query(Candidate)
            .filter(Candidate.candidate_id == candidate_id)
            .first()
        )
        assert db_candidate is not None
        assert db_candidate.candidate_name == "Alice Candidate"
        assert db_interview.candidate_id == db_candidate.id

    # Clean up
    SessionManager.delete_interview(session_id)


def test_4_interview_start():
    """Test starting an interview and verifying status, start_time, and first question."""
    candidate_id = f"cand_{os.urandom(4).hex()}"
    payload = InterviewSessionCreate(
        candidate=CandidateContext(
            candidate_id=candidate_id,
            candidate_name="Bob Developer",
            email="bob@example.com",
            resume_text="Python and backend systems.",
            job_role="Python Engineer",
            job_description="Backend developer."
        ),
        interview_duration=30,
        language="English"
    )

    session = SessionManager.create_session(payload)
    session_id = session["session_id"]

    # Start session
    started = SessionManager.start_session(session_id)
    assert started["status"] == "in_progress"
    assert started["current_question"] is not None

    first_q_id = started["current_question"]["question_id"]

    # Verify in DB
    with get_db_context() as db:
        db_interview = (
            db.query(Interview)
            .filter(Interview.session_id == session_id)
            .first()
        )
        assert db_interview.status == "in_progress"
        assert db_interview.start_time is not None
        assert db_interview.current_question_id == first_q_id

        # Check interview_questions table has the first question stored
        stored_questions = (
            db.query(InterviewQuestion)
            .filter(InterviewQuestion.interview_id == db_interview.id)
            .all()
        )
        assert len(stored_questions) == 1
        assert stored_questions[0].question_id == first_q_id
        assert stored_questions[0].question_type == "primary"
        assert stored_questions[0].sequence_number == 1

    SessionManager.delete_interview(session_id)


@pytest.mark.asyncio
async def test_5_initial_and_followup_answer_persistence():
    """Test answer submission, follow-up progression, and evaluation persistence."""
    candidate_id = f"cand_{os.urandom(4).hex()}"
    payload = InterviewSessionCreate(
        candidate=CandidateContext(
            candidate_id=candidate_id,
            candidate_name="Charlie Test",
            email="charlie@example.com",
            resume_text="Software engineer with Python experience.",
            job_role="Software Engineer",
            job_description="General software engineering."
        ),
        interview_duration=30,
        language="English"
    )

    session = SessionManager.create_session(payload)
    session_id = session["session_id"]
    SessionManager.start_session(session_id)

    # Mock hybrid evaluator to test answer submission, follow-up progression, and persistence
    partial_ai_result = AIEvaluation(
        technical_correctness=60,
        concept_coverage=50,
        reasoning_quality=70,
        communication_clarity=80,
        answer_classification="PARTIAL",
        matched_concepts=["education"],
        missing_concepts=["technical_skills", "projects"],
        incorrect_statements=[],
        evidence=["I have a degree in CS."],
        strengths=["Clear background"],
        improvement_areas=["Mention technical skills"],
        overall_feedback="Partial answer.",
        confidence="high"
    )

    partial_hybrid_result = {
        "rule_evaluation": {"matched_concepts": ["education"], "missing_concepts": ["technical_skills"]},
        "semantic_evaluation": {},
        "contradiction_evaluation": {"has_contradictions": False},
        "ai_evaluation": partial_ai_result.model_dump(),
        "ai_evaluation_triggered": True,
        "ai_evaluation_successful": True,
        "ai_error": None,
        "candidate_evidence": {},
        "decision_evaluation": partial_ai_result.model_dump()
    }

    mock_evaluator = AsyncMock()
    mock_evaluator.evaluate_answer = AsyncMock(return_value=partial_hybrid_result)
    SessionManager._hybrid_evaluator = mock_evaluator

    try:
        result_fu = await SessionManager.submit_answer(
            session_id=session_id,
            answer_text="I graduated in computer science."
        )

        assert result_fu["next_action"] == "FOLLOW_UP"
        assert result_fu["followup_count"] == 1

        # Verify initial answer stored in database
        with get_db_context() as db:
            db_interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .first()
            )
            assert db_interview.followup_count == 1
            assert db_interview.current_followup is not None

            # Verify candidate answer record
            answers = (
                db.query(CandidateAnswer)
                .join(InterviewQuestion)
                .filter(InterviewQuestion.interview_id == db_interview.id)
                .all()
            )
            assert len(answers) == 1
            assert answers[0].answer_type == "initial"
            assert answers[0].answer_text == "I graduated in computer science."

            # Verify evaluation record
            evals = (
                db.query(Evaluation)
                .filter(Evaluation.interview_id == db_interview.id)
                .all()
            )
            assert len(evals) == 1
            assert evals[0].answer_classification == "PARTIAL"

        # Now submit the follow-up answer with a GOOD evaluation
        good_ai_result = AIEvaluation(
            technical_correctness=95,
            concept_coverage=95,
            reasoning_quality=90,
            communication_clarity=95,
            answer_classification="GOOD",
            matched_concepts=["education", "technical_skills", "projects"],
            missing_concepts=[],
            incorrect_statements=[],
            evidence=["Worked with Python, Django and PostgreSQL on web apps."],
            strengths=["Comprehensive explanation"],
            improvement_areas=[],
            overall_feedback="Excellent clarification.",
            confidence="high"
        )

        good_hybrid_result = {
            "rule_evaluation": {"matched_concepts": ["education", "technical_skills", "projects"], "missing_concepts": []},
            "semantic_evaluation": {},
            "contradiction_evaluation": {"has_contradictions": False},
            "ai_evaluation": good_ai_result.model_dump(),
            "ai_evaluation_triggered": True,
            "ai_evaluation_successful": True,
            "ai_error": None,
            "candidate_evidence": {},
            "decision_evaluation": good_ai_result.model_dump()
        }

        mock_evaluator.evaluate_answer = AsyncMock(return_value=good_hybrid_result)

        result_next = await SessionManager.submit_answer(
            session_id=session_id,
            answer_text="I primarily use Python, FastAPI, and PostgreSQL for my projects."
        )

        assert result_next["next_action"] in ["NEXT_QUESTION", "INTERVIEW_COMPLETED"]

        # Verify follow-up answer was persisted
        with get_db_context() as db:
            db_interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .first()
            )
            answers = (
                db.query(CandidateAnswer)
                .join(InterviewQuestion)
                .filter(InterviewQuestion.interview_id == db_interview.id)
                .order_by(CandidateAnswer.created_at.asc())
                .all()
            )
            assert len(answers) == 2
            assert answers[1].answer_type == "follow-up"

            # Verify evaluation updated
            evals = (
                db.query(Evaluation)
                .filter(Evaluation.interview_id == db_interview.id)
                .all()
            )
            assert len(evals) >= 1
            assert evals[0].answer_classification == "GOOD"
    finally:
        SessionManager._hybrid_evaluator = None

    SessionManager.delete_interview(session_id)


def test_6_restart_simulation_and_history_retrieval():
    """
    Test that session state, transcript, questions, answers, and evaluations
    survive complete backend memory clearing (simulating backend restart).
    """
    candidate_id = f"cand_{os.urandom(4).hex()}"
    payload = InterviewSessionCreate(
        candidate=CandidateContext(
            candidate_id=candidate_id,
            candidate_name="Restart Candidate",
            email="restart@example.com",
            resume_text="Python engineer.",
            job_role="Backend Developer",
            job_description="APIs"
        ),
        interview_duration=30,
        language="English"
    )

    session = SessionManager.create_session(payload)
    session_id = session["session_id"]
    SessionManager.start_session(session_id)

    # SIMULATE BACKEND RESTART by completely wiping the in-memory cache
    active_sessions.clear()
    assert len(active_sessions) == 0

    # Retrieve session after memory wipe
    recovered = SessionManager.get_session(session_id)

    assert recovered is not None
    assert recovered["session_id"] == session_id
    assert recovered["status"] == "in_progress"
    assert recovered["candidate"]["candidate_name"] == "Restart Candidate"
    assert recovered["current_question"] is not None
    assert len(recovered["asked_question_ids"]) == 1
    assert len(recovered["transcript"]) >= 1

    # Verify interview history survives restart
    history = SessionManager.get_all_interviews()
    matching = [h for h in history if h["session_id"] == session_id]
    assert len(matching) == 1
    assert matching[0]["candidate_name"] == "Restart Candidate"
    assert matching[0]["status"] == "in_progress"

    # Clean up
    SessionManager.delete_interview(session_id)


def test_7_cascade_deletion():
    """Verify deleting an interview completely deletes associated questions, answers, and evaluations."""
    candidate_id = f"cand_{os.urandom(4).hex()}"
    payload = InterviewSessionCreate(
        candidate=CandidateContext(
            candidate_id=candidate_id,
            candidate_name="Cascade Test",
            email="cascade@example.com",
            resume_text="Tester.",
            job_role="QA",
            job_description="Testing"
        ),
        interview_duration=30,
        language="English"
    )

    session = SessionManager.create_session(payload)
    session_id = session["session_id"]
    SessionManager.start_session(session_id)

    with get_db_context() as db:
        interview = db.query(Interview).filter(Interview.session_id == session_id).first()
        int_id = interview.id

        # Insert dummy answer and evaluation to test cascade
        q = db.query(InterviewQuestion).filter(InterviewQuestion.interview_id == int_id).first()
        ans = CandidateAnswer(question_id=q.id, answer_text="Testing answers", answer_type="initial")
        db.add(ans)
        ev = Evaluation(interview_id=int_id, question_id=q.id, answer_classification="GOOD")
        db.add(ev)

    # Perform cascade deletion
    deleted = SessionManager.delete_interview(session_id)
    assert deleted is True

    # Verify everything was removed
    with get_db_context() as db:
        assert db.query(Interview).filter(Interview.id == int_id).first() is None
        assert db.query(InterviewQuestion).filter(InterviewQuestion.interview_id == int_id).count() == 0
        assert db.query(CandidateAnswer).join(InterviewQuestion).filter(InterviewQuestion.interview_id == int_id).count() == 0
        assert db.query(Evaluation).filter(Evaluation.interview_id == int_id).count() == 0


def test_8_fastapi_endpoints():
    """Test FastAPI API routes with database integration."""
    client = TestClient(app)

    # 1. Health check includes database status
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["database"] == "connected"

    # 2. Create interview via API
    create_payload = {
        "candidate": {
            "candidate_id": f"cand_{os.urandom(4).hex()}",
            "candidate_name": "API Candidate",
            "email": "api@example.com",
            "resume_text": "Full stack engineer",
            "job_role": "Full Stack Engineer",
            "job_description": "React and FastAPI"
        },
        "interview_duration": 40,
        "language": "English"
    }

    res = client.post("/interviews/create", json=create_payload)
    assert res.status_code == 200
    data = res.json()
    session_id = data["session_id"]
    assert data["candidate_name"] == "API Candidate"

    # 3. Get session via API
    res = client.get(f"/interviews/{session_id}")
    assert res.status_code == 200
    assert res.json()["session_id"] == session_id

    # 4. Start interview via API
    res = client.post(f"/interviews/{session_id}/start")
    assert res.status_code == 200
    assert res.json()["status"] == "in_progress"

    # 5. List interviews (history) via API
    res = client.get("/interviews")
    assert res.status_code == 200
    interviews = res.json()["interviews"]
    assert any(i["session_id"] == session_id for i in interviews)

    # 6. Delete interview via API
    res = client.delete(f"/interviews/{session_id}")
    assert res.status_code == 200
    assert res.json()["session_id"] == session_id

    # 7. Verify 404 after deletion
    res = client.get(f"/interviews/{session_id}")
    assert res.status_code == 404
