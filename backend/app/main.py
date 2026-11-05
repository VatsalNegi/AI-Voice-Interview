from fastapi.responses import Response

from app.schemas.voice import SpeechRequest
from app.services.tts_service import TTSService
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException

from app.reporting.report_generator import ReportGenerator

from app.schemas.interview import (
    InterviewSessionCreate,
    InterviewSessionResponse,
    CandidateAnswerSubmit
)

from app.services.session_manager import SessionManager


app = FastAPI(
    title="AI Voice Interview Engine",
    description="An intelligent, adaptive AI-powered voice interview system.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
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
        "status": "success"
    }


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI Voice Interview Engine"
    }


# --------------------------------------------------
# CREATE INTERVIEW SESSION
# --------------------------------------------------

@app.post(
    "/interviews/create",
    response_model=InterviewSessionResponse
)
def create_interview(
    session_data: InterviewSessionCreate
):

    session = SessionManager.create_session(session_data)

    return {
        "session_id": session["session_id"],
        "candidate_name": session["candidate"]["candidate_name"],
        "job_role": session["candidate"]["job_role"],
        "status": session["status"],
        "current_stage": session["current_stage"]
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
            detail="Interview session not found"
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
            detail=str(error)
        )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    return {
        "message": "Interview started successfully",
        "session_id": session["session_id"],
        "status": session["status"],
        "current_stage": session["current_stage"],
        "first_question": session["current_question"]
    }


# --------------------------------------------------
# SUBMIT AND EVALUATE CANDIDATE ANSWER
# --------------------------------------------------

@app.post("/interviews/{session_id}/answer")
async def submit_candidate_answer(
    session_id: str,
    answer_data: CandidateAnswerSubmit
):

    session = SessionManager.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    try:

        result = await SessionManager.submit_answer(
            session_id=session_id,
            answer_text=answer_data.answer_text
        )

        return {
            "message": "Answer submitted successfully",
            "result": result
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


# --------------------------------------------------
# GENERATE HR / TECHNICAL INTERVIEW REPORT
# --------------------------------------------------

@app.get("/interviews/{session_id}/report")
def generate_interview_report(session_id: str):

    session = SessionManager.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Interview session not found"
        )

    if session["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail="Interview must be completed before generating the report."
        )

    try:

        report = ReportGenerator.generate_report(session)

        return {
            "message": "Interview report generated successfully",
            "report": report.model_dump()
        }

    except ValueError as error:

        raise HTTPException(
            status_code=409,
            detail=str(error)
        )
# --------------------------------------------------
# AI INTERVIEWER TEXT-TO-SPEECH
# --------------------------------------------------

@app.post("/voice/speak")
async def generate_interviewer_voice(
    speech_data: SpeechRequest
):

    try:
        audio_bytes, generation_id = (
            await TTSService.generate_speech(
                speech_data.text
            )
        )

        headers = {}

        if generation_id:
            headers["X-Generation-Id"] = generation_id

        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers=headers
        )

    except RuntimeError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error)
        )