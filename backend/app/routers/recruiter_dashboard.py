
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.auth.dependencies import get_current_recruiter
from app.db.session import get_db
from app.db.models import (
    Recruiter,
    Candidate,
    Interview,
    InterviewQuestion,
    CandidateAnswer,
    Evaluation,
)


router = APIRouter(
    prefix="/recruiter",
    tags=["Recruiter Dashboard"],
    dependencies=[Depends(get_current_recruiter)],
)


# --------------------------------------------------
# SERIALIZATION HELPERS
# --------------------------------------------------

def serialize_interview(interview: Interview) -> dict:
    candidate = interview.candidate

    return {
        "session_id": interview.session_id,
        "candidate": {
            "id": candidate.id,
            "candidate_id": candidate.candidate_id,
            "name": candidate.candidate_name,
            "email": candidate.email,
        },
        "job_role": interview.job_role,
        "status": interview.status,
        "current_stage": interview.current_stage,
        "language": interview.language,
        "duration": interview.interview_duration,
        "overall_score": interview.overall_score,
        "recommendation": interview.recommendation,
        "created_at": interview.created_at,
        "start_time": interview.start_time,
        "end_time": interview.end_time,
        "updated_at": interview.updated_at,
    }


# --------------------------------------------------
# DASHBOARD STATISTICS
# --------------------------------------------------

@router.get("/dashboard")
def get_dashboard_statistics(
    db: Session = Depends(get_db),
    recruiter: Recruiter = Depends(get_current_recruiter),
):
    total_interviews = db.query(Interview).count()

    completed_interviews = (
        db.query(Interview)
        .filter(Interview.status == "completed")
        .count()
    )

    in_progress_interviews = (
        db.query(Interview)
        .filter(Interview.status == "in_progress")
        .count()
    )

    not_started_interviews = (
        db.query(Interview)
        .filter(
            Interview.status.in_(["not_started", "pending"])
        )
        .count()
    )

    average_score = (
        db.query(func.avg(Interview.overall_score))
        .filter(
            Interview.status == "completed",
            Interview.overall_score.isnot(None),
        )
        .scalar()
    )

    return {
        "total_interviews": total_interviews,
        "completed_interviews": completed_interviews,
        "in_progress_interviews": in_progress_interviews,
        "not_started_interviews": not_started_interviews,
        "average_score": round(float(average_score), 2)
        if average_score is not None else 0,
    }


# --------------------------------------------------
# INTERVIEW LIST WITH SEARCH AND FILTERS
# --------------------------------------------------

@router.get("/interviews")
def get_recruiter_interviews(
    search: str | None = Query(default=None),
    interview_status: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Interview)
        .options(joinedload(Interview.candidate))
    )

    if search:
        search_term = f"%{search.strip()}%"

        query = query.join(Interview.candidate).filter(
            or_(
                Candidate.candidate_name.ilike(search_term),
                Candidate.email.ilike(search_term),
                Interview.job_role.ilike(search_term),
                Interview.session_id.ilike(search_term),
            )
        )

    if interview_status:
        query = query.filter(
            Interview.status == interview_status
        )

    total = query.count()

    interviews = (
        query
        .order_by(Interview.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "interviews": [
            serialize_interview(interview)
            for interview in interviews
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
        },
    }


# --------------------------------------------------
# COMPLETE INTERVIEW DETAILS
# --------------------------------------------------

@router.get("/interviews/{session_id}")
def get_recruiter_interview_details(
    session_id: str,
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .options(
            joinedload(Interview.candidate),
            joinedload(Interview.questions)
            .joinedload(InterviewQuestion.answers),
            joinedload(Interview.questions)
            .joinedload(InterviewQuestion.evaluations),
            joinedload(Interview.evaluations),
        )
        .filter(Interview.session_id == session_id)
        .first()
    )

    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )

    questions = []

    for question in interview.questions:
        questions.append({
            "id": question.id,
            "question_id": question.question_id,
            "question_text": question.question_text,
            "competency": question.competency,
            "difficulty": question.difficulty,
            "question_type": question.question_type,
            "sequence_number": question.sequence_number,
            "expected_concepts": question.expected_concepts,
            "answers": [
                {
                    "id": answer.id,
                    "answer_text": answer.answer_text,
                    "answer_type": answer.answer_type,
                    "created_at": answer.created_at,
                }
                for answer in question.answers
            ],
            "evaluations": [
                {
                    "id": evaluation.id,
                    "technical_correctness": evaluation.technical_correctness,
                    "concept_coverage": evaluation.concept_coverage,
                    "reasoning_quality": evaluation.reasoning_quality,
                    "communication_clarity": evaluation.communication_clarity,
                    "answer_classification": evaluation.answer_classification,
                    "matched_concepts": evaluation.matched_concepts,
                    "missing_concepts": evaluation.missing_concepts,
                    "incorrect_statements": evaluation.incorrect_statements,
                    "overall_feedback": evaluation.overall_feedback,
                    "confidence": evaluation.confidence,
                    "complete_evaluation": evaluation.complete_evaluation_json,
                }
                for evaluation in question.evaluations
            ],
        })

    return {
        **serialize_interview(interview),
        "job_description": interview.job_description,
        "summary": interview.summary,
        "transcript": interview.transcript or [],
        "final_report": interview.final_report,
        "questions": questions,
        "evaluations": [
            {
                "id": evaluation.id,
                "technical_correctness": evaluation.technical_correctness,
                "concept_coverage": evaluation.concept_coverage,
                "reasoning_quality": evaluation.reasoning_quality,
                "communication_clarity": evaluation.communication_clarity,
                "answer_classification": evaluation.answer_classification,
                "overall_feedback": evaluation.overall_feedback,
                "confidence": evaluation.confidence,
                "complete_evaluation": evaluation.complete_evaluation_json,
                "created_at": evaluation.created_at,
            }
            for evaluation in interview.evaluations
        ],
    }


# --------------------------------------------------
# DELETE INTERVIEW
# --------------------------------------------------

@router.delete("/interviews/{session_id}")
def delete_recruiter_interview(
    session_id: str,
    db: Session = Depends(get_db),
):
    interview = (
        db.query(Interview)
        .filter(Interview.session_id == session_id)
        .first()
    )

    if interview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Interview not found",
        )

    db.delete(interview)
    db.commit()

    return {
        "message": "Interview and related records deleted successfully",
        "session_id": session_id,
    }
