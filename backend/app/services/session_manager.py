from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from app.schemas.interview import InterviewSessionCreate
from app.db.session import get_db_context
from app.db.models import (
    Candidate,
    Interview,
    InterviewQuestion,
    CandidateAnswer,
    Evaluation,
)


# In-memory runtime session cache for performance.
# The database remains the source of truth.
active_sessions: dict[str, dict] = {}


class SessionManager:
    # --------------------------------------------------
    # COMMON HELPERS
    # --------------------------------------------------

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _model_to_session_dict(interview: Interview) -> dict:
        """
        Reconstruct the runtime session dictionary from persistent DB models.

        Answered questions are determined from CandidateAnswer records rather
        than Evaluation records because evaluation now runs after the interview.
        """
        candidate = interview.candidate

        candidate_data = {
            "candidate_id": candidate.candidate_id if candidate else "",
            "candidate_name": candidate.candidate_name if candidate else "",
            "email": candidate.email if candidate else "",
            "resume_text": candidate.resume_text if candidate else "",
            "job_role": interview.job_role,
            "job_description": interview.job_description or "",
        }

        primary_questions = [
            q for q in interview.questions
            if q.question_type == "primary"
        ]

        asked_question_ids = [
            q.question_id
            for q in primary_questions
            if q.asked_at is not None
        ]

        answered_question_ids = [
            q.question_id
            for q in primary_questions
            if q.answers
        ]

        scores = {}
        for evaluation in interview.evaluations:
            if evaluation.question:
                scores[evaluation.question.question_id] = (
                    evaluation.complete_evaluation_json
                    or {
                        "technical_correctness": evaluation.technical_correctness,
                        "concept_coverage": evaluation.concept_coverage,
                        "reasoning_quality": evaluation.reasoning_quality,
                        "communication_clarity": evaluation.communication_clarity,
                        "answer_classification": evaluation.answer_classification,
                        "matched_concepts": evaluation.matched_concepts or [],
                        "missing_concepts": evaluation.missing_concepts or [],
                        "incorrect_statements": evaluation.incorrect_statements or [],
                        "overall_feedback": evaluation.overall_feedback,
                        "confidence": evaluation.confidence,
                        "evaluated_at": (
                            evaluation.created_at.isoformat()
                            if evaluation.created_at
                            else None
                        ),
                    }
                )

        questions_metadata = {}
        for question_record in interview.questions:
            metadata = question_record.metadata_snapshot or {}
            questions_metadata[question_record.question_id] = {
                "question_id": question_record.question_id,
                "question": question_record.question_text,
                "competency": question_record.competency,
                "difficulty": question_record.difficulty,
                "expected_concepts": question_record.expected_concepts or [],
                "sequence_number": question_record.sequence_number,
                "stage": metadata.get("stage", "technical_interview"),
                "stage_label": metadata.get("stage_label", "Technical Interview"),
                "candidate_branch": metadata.get("candidate_branch"),
            }

        return {
            "session_id": interview.session_id,
            "candidate": candidate_data,
            "interview_duration": interview.interview_duration,
            "language": interview.language,
            "status": interview.status,
            "evaluation_status": interview.evaluation_status,
            "preparation_status": interview.preparation_status,
            "preparation_error": interview.preparation_error,
            "prepared_at": (
                interview.prepared_at.isoformat()
                if interview.prepared_at
                else None
            ),
            "total_questions": interview.total_questions or 0,
            "termination_reason": interview.termination_reason,
            "proctoring_violation_count": interview.proctoring_violation_count or 0,
            "terminated_at": (
                interview.terminated_at.isoformat()
                if interview.terminated_at
                else None
            ),
            "tab_switch_count": interview.tab_switch_count or 0,
            "proctoring_paused": bool(interview.proctoring_paused),
            "proctoring_events": interview.proctoring_events or [],
            "current_stage": interview.current_stage,
            "current_question": interview.current_question_metadata,
            "current_followup": None,
            "asked_question_ids": asked_question_ids,
            "answered_question_ids": answered_question_ids,
            "followup_count": 0,
            "current_question_answers": interview.current_question_answers or [],
            "consecutive_unsuccessful_answers": 0,
            "resume_mode": False,
            "resume_question_queue": [],
            "resume_questions_generated": 0,
            "standard_stage_before_resume": interview.current_stage,
            "transcript": interview.transcript or [],
            "scores": scores,
            "questions_metadata": questions_metadata,
            "created_at": (
                interview.created_at.isoformat()
                if interview.created_at
                else None
            ),
            "started_at": (
                interview.start_time.isoformat()
                if interview.start_time
                else None
            ),
            "completed_at": (
                interview.end_time.isoformat()
                if interview.end_time
                else None
            ),
            "overall_score": interview.overall_score,
            "final_report": interview.final_report,
        }

    @staticmethod
    def _append_interviewer_question(interview: Interview, question: dict):
        """Append a predefined question to the persistent transcript."""
        transcript = list(interview.transcript or [])
        transcript.append(
            {
                "speaker": "interviewer",
                "type": "question",
                "question_id": question["question_id"],
                "text": question["question"],
                "timestamp": SessionManager._timestamp(),
            }
        )
        interview.transcript = transcript

    @staticmethod
    def _question_record_to_dict(question_record: InterviewQuestion) -> dict:
        """Convert a persisted question into the runtime/API representation."""
        metadata = question_record.metadata_snapshot or {}

        return {
            "question_id": question_record.question_id,
            "question": question_record.question_text,
            "competency": question_record.competency,
            "difficulty": question_record.difficulty,
            "expected_concepts": question_record.expected_concepts or [],
            "estimated_time_seconds": question_record.estimated_time_seconds,
            "sequence_number": question_record.sequence_number,
            "question_type": question_record.question_type,
            # Defaults preserve compatibility with questions prepared before
            # stage metadata was introduced.
            "stage": metadata.get("stage", "technical_interview"),
            "stage_label": metadata.get("stage_label", "Technical Interview"),
            "candidate_branch": metadata.get("candidate_branch"),
        }

    @staticmethod
    def _activate_question(interview: Interview, question_record: InterviewQuestion):
        """Activate a saved question and set its prepared interview stage."""
        now_dt = datetime.now(timezone.utc)
        question_record.asked_at = now_dt
        question = SessionManager._question_record_to_dict(question_record)

        # Stage is determined during preparation and stored with the question.
        # The live interview does not call an LLM to determine the stage.
        interview.current_stage = question.get(
            "stage",
            "technical_interview",
        )
        interview.current_question_id = question_record.question_id
        interview.current_question_metadata = question
        interview.current_followup = None
        interview.followup_count = 0
        interview.current_question_answers = []

        SessionManager._append_interviewer_question(interview, question)

    # --------------------------------------------------
    # CREATE SESSION
    # --------------------------------------------------

    @staticmethod
    def create_session(session_data: InterviewSessionCreate) -> dict:
        session_id = str(uuid4())
        candidate_data = session_data.candidate.model_dump()

        with get_db_context() as db:
            candidate = (
                db.query(Candidate)
                .filter(Candidate.candidate_id == candidate_data["candidate_id"])
                .first()
            )

            if not candidate:
                candidate = Candidate(
                    candidate_id=candidate_data["candidate_id"],
                    candidate_name=candidate_data["candidate_name"],
                    email=candidate_data["email"],
                    resume_text=candidate_data.get("resume_text", ""),
                )
                db.add(candidate)
                db.flush()
            else:
                candidate.candidate_name = candidate_data["candidate_name"]
                candidate.email = candidate_data["email"]
                if candidate_data.get("resume_text"):
                    candidate.resume_text = candidate_data["resume_text"]
                db.flush()

            interview = Interview(
                session_id=session_id,
                candidate_id=candidate.id,
                job_role=candidate_data["job_role"],
                job_description=candidate_data.get("job_description", ""),
                interview_duration=session_data.interview_duration,
                language=session_data.language,
                status="not_started",
                evaluation_status="not_started",
                preparation_status="pending",
                preparation_error=None,
                prepared_at=None,
                total_questions=0,
                blueprint_metadata=None,
                current_stage="preparation",
                consecutive_unsuccessful_answers=0,
                resume_mode=False,
                resume_questions_generated=0,
                standard_stage_before_resume="preparation",
                current_question_id=None,
                current_question_metadata=None,
                current_followup=None,
                followup_count=0,
                current_question_answers=[],
                resume_question_queue=[],
                transcript=[],
            )
            db.add(interview)
            db.flush()
            db.refresh(interview)
            session_dict = SessionManager._model_to_session_dict(interview)

        active_sessions[session_id] = session_dict
        return session_dict

    # --------------------------------------------------
    # START SESSION
    # --------------------------------------------------

    @staticmethod
    def start_session(session_id: str):
        with get_db_context() as db:
            # Lock only the interviews row. Applying FOR UPDATE to the eager-loaded
            # query below would also affect nullable LEFT OUTER JOIN targets, which
            # PostgreSQL rejects. The row lock remains held for this transaction.
            locked_interview_id = (
                db.query(Interview.id)
                .filter(Interview.session_id == session_id)
                .with_for_update()
                .scalar()
            )

            if locked_interview_id is None:
                return None

            # Load relationships separately, without FOR UPDATE on the joins.
            interview = (
                db.query(Interview)
                .options(
                    joinedload(Interview.candidate),
                    joinedload(Interview.questions).joinedload(InterviewQuestion.answers),
                    joinedload(Interview.evaluations).joinedload(Evaluation.question),
                )
                .filter(Interview.id == locked_interview_id)
                .first()
            )

            if interview is None:
                return None

            if interview.status != "not_started":
                raise ValueError("Interview has already been started or completed.")

            if interview.preparation_status != "ready":
                if interview.preparation_status == "failed":
                    detail = interview.preparation_error or "Question preparation failed."
                    raise ValueError(f"Interview preparation failed: {detail}")
                raise ValueError("Interview questions are still being prepared. Please wait.")

            first_question = (
                db.query(InterviewQuestion)
                .filter(
                    InterviewQuestion.interview_id == interview.id,
                    InterviewQuestion.question_type == "primary",
                )
                .order_by(InterviewQuestion.sequence_number.asc())
                .first()
            )

            if first_question is None:
                raise ValueError("No prepared interview questions were found.")

            if interview.total_questions and interview.total_questions != (
                db.query(InterviewQuestion)
                .filter(
                    InterviewQuestion.interview_id == interview.id,
                    InterviewQuestion.question_type == "primary",
                )
                .count()
            ):
                raise ValueError("Prepared question set is incomplete. Please contact the recruiter.")

            now_dt = datetime.now(timezone.utc)
            interview.status = "in_progress"
            interview.evaluation_status = "not_started"
            interview.start_time = now_dt
            interview.end_time = None

            SessionManager._activate_question(interview, first_question)

            db.flush()
            db.refresh(interview)
            session_dict = SessionManager._model_to_session_dict(interview)

        active_sessions[session_id] = session_dict
        return session_dict

    # --------------------------------------------------
    # SUBMIT ANSWER AND ADVANCE
    # --------------------------------------------------

    @staticmethod
    async def submit_answer(session_id: str, answer_text: str):
        """Persist an answer and activate the next pre-generated question."""
        if not answer_text or not answer_text.strip():
            raise ValueError("Candidate answer cannot be empty.")

        answer_text = answer_text.strip()

        with get_db_context() as db:
            # Lock only the parent interview row. Do not combine FOR UPDATE with
            # joinedload() outer joins on PostgreSQL.
            locked_interview_id = (
                db.query(Interview.id)
                .filter(Interview.session_id == session_id)
                .with_for_update()
                .scalar()
            )

            if locked_interview_id is None:
                raise ValueError("Interview session not found.")

            # Load related records after acquiring the parent-row lock.
            interview = (
                db.query(Interview)
                .options(
                    joinedload(Interview.candidate),
                    joinedload(Interview.questions).joinedload(InterviewQuestion.answers),
                    joinedload(Interview.evaluations).joinedload(Evaluation.question),
                )
                .filter(Interview.id == locked_interview_id)
                .first()
            )

            if interview is None:
                raise ValueError("Interview session not found.")

            if interview.status != "in_progress":
                raise ValueError("Interview is not currently in progress.")

            question_id = interview.current_question_id
            if not question_id:
                raise ValueError("No active question found.")

            question_record = (
                db.query(InterviewQuestion)
                .filter(
                    InterviewQuestion.interview_id == interview.id,
                    InterviewQuestion.question_id == question_id,
                    InterviewQuestion.question_type == "primary",
                )
                .first()
            )

            if question_record is None or question_record.asked_at is None:
                raise ValueError("The active question was not found or was not activated.")

            # Prevent duplicate answer submission for the same active question.
            existing_answer = (
                db.query(CandidateAnswer)
                .filter(CandidateAnswer.question_id == question_record.id)
                .first()
            )
            if existing_answer is not None:
                raise ValueError("An answer has already been submitted for this question.")

            now_dt = datetime.now(timezone.utc)
            db.add(
                CandidateAnswer(
                    question_id=question_record.id,
                    answer_text=answer_text,
                    answer_type="initial",
                    created_at=now_dt,
                )
            )

            transcript = list(interview.transcript or [])
            transcript.append({
                "speaker": "candidate",
                "type": "answer",
                "question_id": question_id,
                "text": answer_text,
                "timestamp": now_dt.isoformat(),
            })
            interview.transcript = transcript
            interview.current_question_answers = [answer_text]

            # Select the next saved question that has not yet been asked.
            next_question = (
                db.query(InterviewQuestion)
                .filter(
                    InterviewQuestion.interview_id == interview.id,
                    InterviewQuestion.question_type == "primary",
                    InterviewQuestion.asked_at.is_(None),
                )
                .order_by(InterviewQuestion.sequence_number.asc())
                .first()
            )

            if next_question is None:
                interview.status = "completed"
                interview.evaluation_status = "pending"
                interview.end_time = now_dt
                interview.current_question_id = None
                interview.current_question_metadata = None
                interview.current_followup = None
                interview.followup_count = 0
                interview.current_question_answers = []
                interview.resume_mode = False
                interview.resume_question_queue = []
                interview.resume_questions_generated = 0

                db.flush()
                db.refresh(interview)
                updated_session = SessionManager._model_to_session_dict(interview)
                active_sessions[session_id] = updated_session

                return {
                    "session_id": session_id,
                    "question_id": question_id,
                    "answer": answer_text,
                    "evaluation": None,
                    "decision": None,
                    "next_action": "INTERVIEW_COMPLETED",
                    "next_question": None,
                    "status": "completed",
                    "evaluation_status": "pending",
                    "answer_classification": None,
                    "consecutive_unsuccessful_answers": 0,
                    "resume_mode": False,
                    "ai_evaluation_successful": None,
                }

            SessionManager._activate_question(interview, next_question)

            db.flush()
            db.refresh(interview)
            updated_session = SessionManager._model_to_session_dict(interview)
            active_sessions[session_id] = updated_session

            return {
                "session_id": session_id,
                "question_id": question_id,
                "answer": answer_text,
                "evaluation": None,
                "decision": None,
                "next_action": "NEXT_QUESTION",
                "next_question": SessionManager._question_record_to_dict(next_question),
                "current_stage": interview.current_stage,
                "evaluation_status": interview.evaluation_status,
                "answer_classification": None,
                "consecutive_unsuccessful_answers": 0,
                "resume_mode": False,
                "ai_evaluation_successful": None,
            }

    # --------------------------------------------------
    # TERMINATE INTERVIEW
    # --------------------------------------------------

    @staticmethod
    def terminate_interview(
        session_id: str,
        reason: str,
        violation_count: int | None = None,
        proctoring_event: dict | None = None,
    ) -> dict | None:
        """Terminate an in-progress interview while preserving its answers."""
        clean_reason = (reason or "").strip()
        if not clean_reason:
            clean_reason = "Interview terminated due to a proctoring violation."

        if violation_count is not None and violation_count < 0:
            raise ValueError("Violation count cannot be negative.")

        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .with_for_update()
                .first()
            )

            if interview is None:
                return None

            # Repeated termination requests are safe and idempotent.
            if interview.status == "terminated":
                session_dict = SessionManager._model_to_session_dict(interview)
                active_sessions[session_id] = session_dict
                return session_dict

            if interview.status != "in_progress":
                raise ValueError(
                    "Only an in-progress interview can be terminated."
                )

            now_dt = datetime.now(timezone.utc)
            events = list(interview.proctoring_events or [])

            if proctoring_event:
                events.append(dict(proctoring_event))

            events.append({
                "type": "interview_terminated",
                "reason": clean_reason,
                "violation_count": (
                    violation_count
                    if violation_count is not None
                    else interview.proctoring_violation_count or 0
                ),
                "timestamp": now_dt.isoformat(),
            })

            interview.status = "terminated"
            interview.evaluation_status = "skipped"
            interview.termination_reason = clean_reason
            interview.terminated_at = now_dt
            interview.end_time = now_dt
            interview.proctoring_paused = True
            interview.proctoring_events = events

            if violation_count is not None:
                interview.proctoring_violation_count = violation_count

            # Clear active-question state without deleting answers or transcript.
            interview.current_question_id = None
            interview.current_question_metadata = None
            interview.current_followup = None
            interview.followup_count = 0
            interview.current_question_answers = []
            interview.resume_mode = False
            interview.resume_question_queue = []
            interview.resume_questions_generated = 0

            # No normal AI report or hiring recommendation for terminated sessions.
            interview.overall_score = None
            interview.recommendation = None
            interview.final_report = None
            interview.summary = None

            db.flush()
            db.refresh(interview)
            session_dict = SessionManager._model_to_session_dict(interview)

        active_sessions[session_id] = session_dict
        return session_dict

    # --------------------------------------------------
    # GET SESSION
    # --------------------------------------------------

    @staticmethod
    def get_session(session_id: str) -> dict | None:
        """
        Retrieve the session from the database.
        The in-memory cache is only a fallback.
        """
        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .options(
                    joinedload(Interview.candidate),
                    joinedload(Interview.questions).joinedload(
                        InterviewQuestion.answers
                    ),
                    joinedload(Interview.evaluations).joinedload(
                        Evaluation.question
                    ),
                )
                .filter(Interview.session_id == session_id)
                .first()
            )

            if interview is not None:
                session_dict = SessionManager._model_to_session_dict(
                    interview
                )
                active_sessions[session_id] = session_dict
                return session_dict

        return active_sessions.get(session_id)

    # --------------------------------------------------
    # UPDATE SESSION
    # --------------------------------------------------

    @staticmethod
    def update_session(session_id: str, updates: dict):
        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .first()
            )

            if interview is not None:
                for key, value in updates.items():
                    if hasattr(interview, key):
                        setattr(interview, key, value)

                db.flush()
                db.refresh(interview)

                session_dict = SessionManager._model_to_session_dict(
                    interview
                )
                active_sessions[session_id] = session_dict
                return session_dict

        session = active_sessions.get(session_id)
        if session is not None:
            session.update(updates)
            return session

        return None

    # --------------------------------------------------
    # RETRIEVE INTERVIEW HISTORY
    # --------------------------------------------------

    @staticmethod
    def get_all_interviews() -> list[dict]:
        """Retrieve interview records from PostgreSQL for recruiter history."""
        with get_db_context() as db:
            interviews = (
                db.query(Interview)
                .options(joinedload(Interview.candidate))
                .order_by(Interview.created_at.desc())
                .all()
            )

            history = []
            for interview in interviews:
                candidate = interview.candidate
                history.append(
                    {
                        "session_id": interview.session_id,
                        "candidate_id": (
                            candidate.candidate_id if candidate else ""
                        ),
                        "candidate_name": (
                            candidate.candidate_name
                            if candidate
                            else "Unknown"
                        ),
                        "email": candidate.email if candidate else "",
                        "job_role": interview.job_role,
                        "status": interview.status,
                        "evaluation_status": interview.evaluation_status,
                        "termination_reason": interview.termination_reason,
                        "proctoring_violation_count": (
                            interview.proctoring_violation_count or 0
                        ),
                        "terminated_at": (
                            interview.terminated_at.isoformat()
                            if interview.terminated_at
                            else None
                        ),
                        "tab_switch_count": interview.tab_switch_count or 0,
                        "current_stage": interview.current_stage,
                        "overall_score": interview.overall_score,
                        "start_time": (
                            interview.start_time.isoformat()
                            if interview.start_time
                            else None
                        ),
                        "end_time": (
                            interview.end_time.isoformat()
                            if interview.end_time
                            else None
                        ),
                        "created_at": (
                            interview.created_at.isoformat()
                            if interview.created_at
                            else None
                        ),
                        "updated_at": (
                            interview.updated_at.isoformat()
                            if interview.updated_at
                            else None
                        ),
                    }
                )

            return history

    # --------------------------------------------------
    # DELETE INTERVIEW
    # --------------------------------------------------

    @staticmethod
    def delete_interview(session_id: str) -> bool:
        """
        Delete an interview and its related questions, answers, and evaluations.
        Database cascade rules handle the related records.
        """
        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .first()
            )

            if interview is None:
                return False

            db.delete(interview)

        active_sessions.pop(session_id, None)
        return True
