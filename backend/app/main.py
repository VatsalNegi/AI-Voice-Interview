from app.routers.recruiter_dashboard import router as recruiter_dashboard_router
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.db.models import Recruiter

from app.auth.security import (
    verify_password,
    create_access_token,
)
from app.auth.dependencies import get_current_recruiter

from app.schemas.auth import (
    RecruiterLogin,
    TokenResponse,
    RecruiterResponse,
)

from app.schemas.voice import SpeechRequest
from app.schemas.interview import (
    InterviewSessionCreate,
    InterviewSessionResponse,
    CandidateAnswerSubmit,
)

from app.services.tts_service import TTSService
from app.services.session_manager import SessionManager
from app.services.post_interview_evaluator import PostInterviewEvaluator


class InterviewTerminationRequest(BaseModel):
    reason: str
    violation_count: int | None = Field(default=None, ge=0)
    proctoring_event: dict | None = None


# --------------------------------------------------
# APPLICATION LIFESPAN
# --------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database connection successful.")
    except Exception as exc:
        print(f"Database connection check warning: {exc}")

    yield


app = FastAPI(
    title="AI Voice Interview Engine",
    description="An intelligent, adaptive AI-powered voice interview system.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(recruiter_dashboard_router)


# --------------------------------------------------
# CORS
# --------------------------------------------------

# Keep local development origins and add deployed frontend origin(s)
# through FRONTEND_URL. Multiple origins can be comma-separated.
frontend_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_URL", "").split(",")
    if origin.strip()
]

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    *frontend_origins,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# HOME
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "AI Voice Interview Engine is running!",
        "status": "success",
    }


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health_check():
    db_status = "connected"

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    return {
        "status": "healthy",
        "service": "AI Voice Interview Engine",
        "database": db_status,
    }


# ==================================================
# RECRUITER AUTHENTICATION
# ==================================================


# --------------------------------------------------
# RECRUITER LOGIN
# --------------------------------------------------

@app.post(
    "/auth/login",
    response_model=TokenResponse,
)
def recruiter_login(
    login_data: RecruiterLogin,
    db: Session = Depends(get_db),
):
    email = login_data.email.strip().lower()

    recruiter = (
        db.query(Recruiter)
        .filter(Recruiter.email == email)
        .first()
    )

    if recruiter is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not recruiter.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This recruiter account is inactive.",
        )

    if not verify_password(
        login_data.password,
        recruiter.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    access_token = create_access_token(recruiter.id)

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# --------------------------------------------------
# GET LOGGED-IN RECRUITER
# --------------------------------------------------

@app.get(
    "/auth/me",
    response_model=RecruiterResponse,
)
def get_logged_in_recruiter(
    recruiter: Recruiter = Depends(get_current_recruiter),
):
    return recruiter


# ==================================================
# CANDIDATE INTERVIEW APIs
# These remain publicly accessible.
# ==================================================


# --------------------------------------------------
# CREATE INTERVIEW SESSION
# --------------------------------------------------

@app.post(
    "/interviews/create",
    response_model=InterviewSessionResponse,
)
def create_interview(
    session_data: InterviewSessionCreate,
):
    session = SessionManager.create_session(session_data)

    return {
        "session_id": session["session_id"],
        "candidate_name": session["candidate"]["candidate_name"],
        "job_role": session["candidate"]["job_role"],
        "status": session["status"],
        "current_stage": session["current_stage"],
    }


# --------------------------------------------------
# GET INTERVIEW SESSION
# --------------------------------------------------

@app.get("/interviews/{session_id}")
def get_interview(session_id: str):
    session = SessionManager.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found",
        )

    return session


# --------------------------------------------------
# START INTERVIEW
# --------------------------------------------------

@app.post("/interviews/{session_id}/start")
def start_interview(session_id: str):
    try:
        session = SessionManager.start_session(session_id)

    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found",
        )

    return {
        "message": "Interview started successfully",
        "session_id": session["session_id"],
        "status": session["status"],
        "current_stage": session["current_stage"],
        "first_question": session["current_question"],
    }


# --------------------------------------------------
# SUBMIT CANDIDATE ANSWER
# --------------------------------------------------

@app.post("/interviews/{session_id}/answer")
async def submit_candidate_answer(
    session_id: str,
    answer_data: CandidateAnswerSubmit,
    background_tasks: BackgroundTasks,
):
    session = SessionManager.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found",
        )

    try:
        result = await SessionManager.submit_answer(
            session_id=session_id,
            answer_text=answer_data.answer_text,
        )

        # The live interview has finished. Run the AI evaluation after
        # the response is prepared, so the candidate does not wait for it.
        if result.get("status") == "completed":
            background_tasks.add_task(
                PostInterviewEvaluator.run,
                session_id,
            )

        return {
            "message": "Answer submitted successfully",
            "result": result,
        }

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


# --------------------------------------------------
# TERMINATE INTERVIEW
# Terminated interviews retain answers/transcript but skip AI evaluation.
# --------------------------------------------------

@app.post("/interviews/{session_id}/terminate")
def terminate_interview(
    session_id: str,
    termination_data: InterviewTerminationRequest,
):
    session = SessionManager.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found",
        )

    try:
        terminated_session = SessionManager.terminate_interview(
            session_id=session_id,
            reason=termination_data.reason,
            violation_count=termination_data.violation_count,
            proctoring_event=termination_data.proctoring_event,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )

    if terminated_session is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found",
        )

    return {
        "message": "Interview terminated successfully",
        "session_id": terminated_session["session_id"],
        "status": terminated_session["status"],
        "evaluation_status": terminated_session.get("evaluation_status"),
        "termination_reason": terminated_session.get("termination_reason"),
        "proctoring_violation_count": terminated_session.get(
            "proctoring_violation_count", 0
        ),
        "terminated_at": terminated_session.get("terminated_at"),
        "transcript_preserved": True,
    }


# --------------------------------------------------
# INTERVIEW REPORT
# Evaluation is performed asynchronously after completion.
# --------------------------------------------------

@app.get("/interviews/{session_id}/report")
def get_interview_report(session_id: str):
    session = SessionManager.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found",
        )

    if session["status"] == "terminated":
        raise HTTPException(
            status_code=409,
            detail="This interview was terminated. Its answers and transcript are retained, but no hiring evaluation or recommendation is generated.",
        )

    if session["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail="Interview must be completed before the report is available.",
        )

    evaluation_status = session.get("evaluation_status")
    final_report = session.get("final_report")

    if evaluation_status == "completed" and final_report:
        return {
            "message": "Interview report generated successfully",
            "evaluation_status": "completed",
            "report": final_report,
        }

    if evaluation_status in {"pending", "processing", "not_started"}:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "message": "Interview completed. AI evaluation is still processing.",
                "evaluation_status": evaluation_status,
                "report": None,
            },
        )

    if evaluation_status == "failed":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "message": "The interview evaluation failed. Please check the backend logs.",
                "evaluation_status": "failed",
                "report": None,
            },
        )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "message": "The interview report is not ready yet.",
            "evaluation_status": evaluation_status or "unknown",
            "report": None,
        },
    )


# ==================================================
# PROTECTED RECRUITER APIs
# ==================================================


# --------------------------------------------------
# LIST ALL INTERVIEWS
# --------------------------------------------------

@app.get("/interviews")
def list_interviews(
    recruiter: Recruiter = Depends(get_current_recruiter),
):
    interviews = SessionManager.get_all_interviews()

    return {
        "message": "Interview history retrieved successfully",
        "interviews": interviews,
    }


# --------------------------------------------------
# DELETE INTERVIEW
# --------------------------------------------------

@app.delete("/interviews/{session_id}")
def delete_interview(
    session_id: str,
    recruiter: Recruiter = Depends(get_current_recruiter),
):
    deleted = SessionManager.delete_interview(session_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found",
        )

    return {
        "message": "Interview and all related records deleted successfully",
        "session_id": session_id,
    }


# ==================================================
# AI INTERVIEWER TEXT-TO-SPEECH
# ==================================================

@app.post("/voice/speak")
async def generate_interviewer_voice(
    speech_data: SpeechRequest,
):
    try:
        audio_bytes, generation_id = (
            await TTSService.generate_speech(speech_data.text)
        )

        headers = {}

        if generation_id:
            headers["X-Generation-Id"] = generation_id

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers=headers,
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        )
