from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.orm import joinedload
from app.schemas.interview import InterviewSessionCreate
from app.engine.question_selector import QuestionSelector
from app.engine.decision_engine import DecisionEngine
from app.config.question_bank import QUESTION_BANK

from app.db.session import get_db_context
from app.db.models import (
    Candidate,
    Interview,
    InterviewQuestion,
    CandidateAnswer,
    Evaluation,
)

# In-memory runtime session cache for performance
active_sessions: dict[str, dict] = {}


class SessionManager:

    _hybrid_evaluator = None
    _resume_question_generator = None

    RESUME_FALLBACK_THRESHOLD = 5
    RESUME_QUESTION_BATCH_SIZE = 3

    # --------------------------------------------------
    # SERVICE INITIALIZATION
    # --------------------------------------------------

    @classmethod
    def _get_hybrid_evaluator(cls):
        if cls._hybrid_evaluator is None:
            from app.services.hybrid_evaluator import HybridEvaluator
            cls._hybrid_evaluator = HybridEvaluator()
        return cls._hybrid_evaluator

    @classmethod
    def _get_resume_question_generator(cls):
        if cls._resume_question_generator is None:
            from app.services.resume_question_generator import ResumeQuestionGenerator
            cls._resume_question_generator = ResumeQuestionGenerator()
        return cls._resume_question_generator

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat()

    # --------------------------------------------------
    # RECONSTRUCT SESSION DICT FROM DB MODEL
    # --------------------------------------------------

    @staticmethod
    def _model_to_session_dict(interview: Interview) -> dict:
        """
        Reconstructs the complete session dictionary from persistent DB models.
        Preserves compatibility with the existing application logic and frontend.
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

        # Asked questions and answered questions tracking
        primary_questions = [
            q for q in interview.questions if q.question_type == "primary"
        ]
        asked_question_ids = [q.question_id for q in primary_questions]

        # Questions that have evaluations are considered answered
        eval_question_id_map = {}
        for ev in interview.evaluations:
            if ev.question:
                eval_question_id_map[ev.question.question_id] = ev

        answered_question_ids = [
            qid for qid in asked_question_ids if qid in eval_question_id_map
        ]

        # Scores dictionary: question_id -> stored_evaluation
        scores = {}
        for ev in interview.evaluations:
            if ev.question:
                scores[ev.question.question_id] = ev.complete_evaluation_json or {
                    "technical_correctness": ev.technical_correctness,
                    "concept_coverage": ev.concept_coverage,
                    "reasoning_quality": ev.reasoning_quality,
                    "communication_clarity": ev.communication_clarity,
                    "answer_classification": ev.answer_classification,
                    "matched_concepts": ev.matched_concepts or [],
                    "missing_concepts": ev.missing_concepts or [],
                    "incorrect_statements": ev.incorrect_statements or [],
                    "overall_feedback": ev.overall_feedback,
                    "confidence": ev.confidence,
                    "evaluated_at": ev.created_at.isoformat() if ev.created_at else None,
                }

        # Stored questions metadata for resume and bank lookup
        questions_metadata = {}
        for q in interview.questions:
            questions_metadata[q.question_id] = {
                "question_id": q.question_id,
                "question": q.question_text,
                "competency": q.competency,
                "difficulty": q.difficulty,
                "expected_concepts": q.expected_concepts or [],
            }

        return {
            "session_id": interview.session_id,
            "candidate": candidate_data,
            "interview_duration": interview.interview_duration,
            "language": interview.language,
            "status": interview.status,
            "current_stage": interview.current_stage,
            "current_question": interview.current_question_metadata,
            "current_followup": interview.current_followup,
            "asked_question_ids": asked_question_ids,
            "answered_question_ids": answered_question_ids,
            "followup_count": interview.followup_count,
            "current_question_answers": interview.current_question_answers or [],
            "consecutive_unsuccessful_answers": interview.consecutive_unsuccessful_answers,
            "resume_mode": interview.resume_mode,
            "resume_question_queue": interview.resume_question_queue or [],
            "resume_questions_generated": interview.resume_questions_generated,
            "standard_stage_before_resume": interview.standard_stage_before_resume,
            "transcript": interview.transcript or [],
            "scores": scores,
            "questions_metadata": questions_metadata,
            "created_at": interview.created_at.isoformat() if interview.created_at else None,
            "started_at": interview.start_time.isoformat() if interview.start_time else None,
            "completed_at": interview.end_time.isoformat() if interview.end_time else None,
            "overall_score": interview.overall_score,
            "final_report": interview.final_report,
        }

    # --------------------------------------------------
    # RESUME EXTRACTION
    # --------------------------------------------------

    @staticmethod
    def _get_resume_text(session):
        candidate = session.get("candidate", {})
        if not isinstance(candidate, dict):
            return ""

        resume_text = (
            candidate.get("resume_text")
            or candidate.get("resume")
            or ""
        )
        if not isinstance(resume_text, str):
            return ""
        return resume_text.strip()

    # --------------------------------------------------
    # BUILD FOLLOW-UP QUESTION
    # --------------------------------------------------

    @staticmethod
    def _build_followup_question(missing_concepts):
        if not missing_concepts:
            return "Could you elaborate a little more on your answer?"

        concepts = [
            str(concept).replace("_", " ")
            for concept in missing_concepts[:2]
        ]

        if len(concepts) == 1:
            return f"Could you explain a little more about {concepts[0]}?"

        return f"Could you explain a little more about {concepts[0]} and {concepts[1]}?"

    # --------------------------------------------------
    # SET NEXT QUESTION
    # --------------------------------------------------

    @staticmethod
    def _set_next_question(session, question, stage):
        session["current_stage"] = stage
        session["current_question"] = question
        session["current_followup"] = None

        session["followup_count"] = 0
        session["current_question_answers"] = []

        question_id = question["question_id"]

        if question_id not in session["asked_question_ids"]:
            session["asked_question_ids"].append(question_id)

        session["transcript"].append({
            "speaker": "interviewer",
            "type": "question",
            "question_id": question_id,
            "text": question["question"],
            "timestamp": SessionManager._timestamp()
        })

        return question

    # --------------------------------------------------
    # GENERATE RESUME QUESTIONS
    # --------------------------------------------------

    @staticmethod
    async def _generate_resume_question_batch(session):
        resume_text = SessionManager._get_resume_text(session)
        if not resume_text:
            print(
                "Resume fallback unavailable: "
                "Candidate resume text was not provided."
            )
            return []

        asked_questions = [
            item["text"]
            for item in session.get("transcript", [])
            if (
                item.get("speaker") == "interviewer"
                and item.get("type") == "question"
            )
        ]

        generator = SessionManager._get_resume_question_generator()
        generated_questions = await generator.generate_questions(
            resume_text=resume_text,
            asked_questions=asked_questions,
            count=SessionManager.RESUME_QUESTION_BATCH_SIZE
        )

        prepared_questions = []
        for item in generated_questions:
            question_number = session.get("resume_questions_generated", 0) + 1
            question = {
                "question_id": f"RESUME_{question_number:03d}",
                "question": item["question"],
                "expected_concepts": item["expected_concepts"],
                "competency": item.get(
                    "competency",
                    "Resume-Based Technical Knowledge"
                ),
                "difficulty": item.get("difficulty", "medium"),
                "max_followups": 1,
                "source": "resume"
            }
            session["resume_questions_generated"] = question_number
            prepared_questions.append(question)

        print(f"Generated {len(prepared_questions)} resume-based questions.")
        return prepared_questions

    # --------------------------------------------------
    # GET NEXT RESUME QUESTION
    # --------------------------------------------------

    @staticmethod
    async def _get_next_resume_question(session):
        queue = session.get("resume_question_queue", [])
        if not queue:
            generated_questions = (
                await SessionManager._generate_resume_question_batch(session)
            )
            queue.extend(generated_questions)
            session["resume_question_queue"] = queue

        if not queue:
            return None

        question = queue.pop(0)
        session["resume_question_queue"] = queue

        return SessionManager._set_next_question(
            session,
            question,
            "resume_based"
        )

    # --------------------------------------------------
    # ADVANCE TO NEXT QUESTION
    # --------------------------------------------------

    @staticmethod
    async def _advance_to_next_question(session):
        failure_count = session.get("consecutive_unsuccessful_answers", 0)
        resume_text = SessionManager._get_resume_text(session)

        # ----------------------------------------------
        # RESUME FALLBACK
        # ----------------------------------------------
        if (
            failure_count >= SessionManager.RESUME_FALLBACK_THRESHOLD
            and resume_text
        ):
            session["resume_mode"] = True
            resume_question = await SessionManager._get_next_resume_question(session)
            if resume_question is not None:
                return resume_question

            print(
                "Resume question generation unavailable. "
                "Falling back to the normal question bank."
            )

        # ----------------------------------------------
        # NORMAL QUESTION BANK
        # ----------------------------------------------
        stages = list(QUESTION_BANK.keys())
        current_stage = session.get("current_stage", "introduction")

        if current_stage == "resume_based":
            current_stage = session.get(
                "standard_stage_before_resume",
                "introduction"
            )

        if current_stage not in stages:
            current_stage = "introduction" if stages else None

        if not stages or current_stage is None:
            session["status"] = "completed"
            session["current_question"] = None
            session["current_followup"] = None
            session["completed_at"] = SessionManager._timestamp()
            return None

        # Try another question in current stage
        question = QuestionSelector.select_next_question(
            stage=current_stage,
            asked_question_ids=session["asked_question_ids"]
        )

        if question is not None:
            return SessionManager._set_next_question(
                session,
                question,
                current_stage
            )

        # Move to the next stage
        current_index = stages.index(current_stage)
        for stage in stages[current_index + 1:]:
            question = QuestionSelector.select_next_question(
                stage=stage,
                asked_question_ids=session["asked_question_ids"]
            )
            if question is not None:
                return SessionManager._set_next_question(
                    session,
                    question,
                    stage
                )

        # No questions remain
        session["status"] = "completed"
        session["current_question"] = None
        session["current_followup"] = None
        session["completed_at"] = SessionManager._timestamp()
        return None

    # --------------------------------------------------
    # UPDATE FAILURE COUNTER
    # --------------------------------------------------

    @staticmethod
    def _update_failure_counter(session, evaluation):
        classification = str(
            evaluation.get("answer_classification", "")
        ).upper().strip()

        if classification == "GOOD":
            session["consecutive_unsuccessful_answers"] = 0
            print("Good answer received. Failure counter reset.")
        elif classification in ["IRRELEVANT", "NO_KNOWLEDGE"]:
            session["consecutive_unsuccessful_answers"] = (
                session.get("consecutive_unsuccessful_answers", 0) + 1
            )
            print(
                f"Unsuccessful primary question. "
                f"Consecutive failures: {session['consecutive_unsuccessful_answers']}"
            )

        return session.get("consecutive_unsuccessful_answers", 0)

    # --------------------------------------------------
    # CREATE SESSION (DATABASE PERSISTENCE)
    # --------------------------------------------------

    @staticmethod
    def create_session(session_data: InterviewSessionCreate) -> dict:
        session_id = str(uuid4())
        candidate_data = session_data.candidate.model_dump()

        with get_db_context() as db:
            # Check or create candidate in database
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
                # Update candidate information if necessary
                candidate.candidate_name = candidate_data["candidate_name"]
                candidate.email = candidate_data["email"]
                if candidate_data.get("resume_text"):
                    candidate.resume_text = candidate_data["resume_text"]
                db.flush()

            # Create persistent interview record
            interview = Interview(
                session_id=session_id,
                candidate_id=candidate.id,
                job_role=candidate_data["job_role"],
                job_description=candidate_data.get("job_description", ""),
                interview_duration=session_data.interview_duration,
                language=session_data.language,
                status="not_started",
                current_stage="introduction",
                consecutive_unsuccessful_answers=0,
                resume_mode=False,
                resume_questions_generated=0,
                standard_stage_before_resume="introduction",
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

            # Eagerly load relationship for reconstruction
            db.refresh(interview)
            session_dict = SessionManager._model_to_session_dict(interview)

        active_sessions[session_id] = session_dict
        return session_dict

    # --------------------------------------------------
    # START SESSION (DATABASE PERSISTENCE)
    # --------------------------------------------------

    @staticmethod
    def start_session(session_id: str):
        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .options(
                    joinedload(Interview.candidate),
                    joinedload(Interview.questions),
                    joinedload(Interview.evaluations),
                )
                .filter(Interview.session_id == session_id)
                .first()
            )

            if interview is None:
                return None

            if interview.status != "not_started":
                raise ValueError(
                    "Interview has already been started or completed."
                )

            asked_question_ids = [
                q.question_id
                for q in interview.questions
                if q.question_type == "primary"
            ]

            question = QuestionSelector.select_next_question(
                stage=interview.current_stage,
                asked_question_ids=asked_question_ids
            )

            if question is None:
                raise ValueError(
                    f"No questions available for stage: {interview.current_stage}"
                )

            now_dt = datetime.now(timezone.utc)
            interview.status = "in_progress"
            interview.start_time = now_dt
            interview.current_question_id = question["question_id"]
            interview.current_question_metadata = question
            interview.current_followup = None
            interview.followup_count = 0
            interview.current_question_answers = []

            # Store the question in interview_questions table
            first_q_record = InterviewQuestion(
                interview_id=interview.id,
                question_id=question["question_id"],
                question_text=question["question"],
                competency=question.get("competency"),
                difficulty=question.get("difficulty"),
                question_type="primary",
                sequence_number=1,
                expected_concepts=question.get("expected_concepts"),
                created_at=now_dt
            )
            db.add(first_q_record)

            # Update transcript
            transcript = list(interview.transcript or [])
            transcript.append({
                "speaker": "interviewer",
                "type": "question",
                "question_id": question["question_id"],
                "text": question["question"],
                "timestamp": now_dt.isoformat()
            })
            interview.transcript = transcript

            db.flush()
            db.refresh(interview)
            session_dict = SessionManager._model_to_session_dict(interview)

        active_sessions[session_id] = session_dict
        return session_dict

    # --------------------------------------------------
    # SUBMIT AND EVALUATE ANSWER (DATABASE PERSISTENCE)
    # --------------------------------------------------

    @staticmethod
    async def submit_answer(session_id: str, answer_text: str):
        # 1. Fetch current interview state from DB
        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .options(
                    joinedload(Interview.candidate),
                    joinedload(Interview.questions).joinedload(InterviewQuestion.answers),
                    joinedload(Interview.evaluations),
                )
                .filter(Interview.session_id == session_id)
                .first()
            )

            if interview is None:
                raise ValueError("Interview session not found.")

            if interview.status != "in_progress":
                raise ValueError("Interview is not currently in progress.")

            question = interview.current_question_metadata
            if question is None:
                raise ValueError("No active question found.")

            question_id = question["question_id"]

            if not answer_text or not answer_text.strip():
                raise ValueError("Candidate answer cannot be empty.")

            answer_text = answer_text.strip()

            # Find the primary question record
            primary_q_record = (
                db.query(InterviewQuestion)
                .filter(
                    InterviewQuestion.interview_id == interview.id,
                    InterviewQuestion.question_id == question_id,
                    InterviewQuestion.question_type == "primary",
                )
                .order_by(InterviewQuestion.sequence_number.desc())
                .first()
            )

            if primary_q_record is None:
                raise ValueError(f"Primary question {question_id} not found in database.")

            primary_q_id = primary_q_record.id
            primary_q_competency = primary_q_record.competency
            primary_q_difficulty = primary_q_record.difficulty

            # Determine whether this is an initial answer or follow-up answer
            answer_type = "follow-up" if interview.current_followup else "initial"

            # 2. Persist candidate answer to candidate_answers table
            now_dt = datetime.now(timezone.utc)
            cand_answer_record = CandidateAnswer(
                question_id=primary_q_id,
                answer_text=answer_text,
                answer_type=answer_type,
                created_at=now_dt
            )
            db.add(cand_answer_record)

            # Update interview transcript and current question answers
            transcript = list(interview.transcript or [])
            transcript.append({
                "speaker": "candidate",
                "type": "answer",
                "question_id": question_id,
                "text": answer_text,
                "timestamp": now_dt.isoformat()
            })
            interview.transcript = transcript

            current_question_answers = list(interview.current_question_answers or [])
            current_question_answers.append(answer_text)
            interview.current_question_answers = current_question_answers
            combined_answer = " ".join(current_question_answers)

            # Reconstruct session representation for evaluator / decision engine
            session = SessionManager._model_to_session_dict(interview)
            session["current_question_answers"] = current_question_answers

            interview_db_id = interview.id

        # 3. Hybrid evaluation (outside DB lock to avoid holding transaction during LLM call)
        hybrid_evaluator = SessionManager._get_hybrid_evaluator()
        hybrid_result = await hybrid_evaluator.evaluate_answer(
            question=question,
            candidate_answer=combined_answer
        )
        decision_evaluation = hybrid_result["decision_evaluation"].copy()

        stored_evaluation = {
            **decision_evaluation,
            "candidate_answer": combined_answer,
            "hybrid_evaluation": hybrid_result,
            "evaluated_at": SessionManager._timestamp()
        }

        # 4. Decision Engine
        decision = DecisionEngine.decide_next_action(
            question=question,
            evaluation=decision_evaluation,
            followup_count=session["followup_count"]
        )

        # 5. Persist evaluation and next state in DB transaction
        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .options(
                    joinedload(Interview.candidate),
                    joinedload(Interview.questions),
                    joinedload(Interview.evaluations),
                )
                .filter(Interview.id == interview_db_id)
                .first()
            )

            # Persist or update Evaluation in database
            eval_record = (
                db.query(Evaluation)
                .filter(
                    Evaluation.interview_id == interview.id,
                    Evaluation.question_id == primary_q_id
                )
                .first()
            )

            if eval_record is None:
                eval_record = Evaluation(
                    interview_id=interview.id,
                    question_id=primary_q_id,
                )
                db.add(eval_record)

            eval_record.technical_correctness = decision_evaluation.get("technical_correctness")
            eval_record.concept_coverage = decision_evaluation.get("concept_coverage")
            eval_record.reasoning_quality = decision_evaluation.get("reasoning_quality")
            eval_record.communication_clarity = decision_evaluation.get("communication_clarity")
            eval_record.answer_classification = decision_evaluation.get("answer_classification")
            eval_record.matched_concepts = decision_evaluation.get("matched_concepts", [])
            eval_record.missing_concepts = decision_evaluation.get("missing_concepts", [])
            eval_record.incorrect_statements = decision_evaluation.get("incorrect_statements", [])
            eval_record.overall_feedback = decision_evaluation.get("overall_feedback")
            eval_record.confidence = decision_evaluation.get("confidence")
            eval_record.complete_evaluation_json = stored_evaluation
            eval_record.created_at = datetime.now(timezone.utc)

            # ------------------------------------------
            # CASE 1: FOLLOW-UP
            # ------------------------------------------
            if decision["action"] == "FOLLOW_UP":
                interview.followup_count += 1
                followup_question = SessionManager._build_followup_question(
                    decision["target_concepts"]
                )
                interview.current_followup = followup_question

                # Persist follow-up question in interview_questions table
                seq_count = (
                    db.query(InterviewQuestion)
                    .filter(InterviewQuestion.interview_id == interview.id)
                    .count()
                )
                fu_q_record = InterviewQuestion(
                    interview_id=interview.id,
                    question_id=f"{question_id}_followup",
                    question_text=followup_question,
                    competency=primary_q_competency,
                    difficulty=primary_q_difficulty,
                    question_type="follow-up",
                    sequence_number=seq_count + 1,
                    expected_concepts=decision.get("target_concepts", []),
                )
                db.add(fu_q_record)

                transcript = list(interview.transcript or [])
                transcript.append({
                    "speaker": "interviewer",
                    "type": "follow_up",
                    "question_id": question_id,
                    "text": followup_question,
                    "timestamp": SessionManager._timestamp()
                })
                interview.transcript = transcript

                db.flush()
                db.refresh(interview)
                updated_session = SessionManager._model_to_session_dict(interview)
                active_sessions[session_id] = updated_session

                return {
                    "session_id": session_id,
                    "question_id": question_id,
                    "answer": answer_text,
                    "evaluation": stored_evaluation,
                    "decision": decision,
                    "next_action": "FOLLOW_UP",
                    "next_question": followup_question,
                    "followup_count": interview.followup_count,
                    "ai_evaluation_successful": hybrid_result["ai_evaluation_successful"]
                }

            # ------------------------------------------
            # CASE 2: PRIMARY QUESTION COMPLETED
            # ------------------------------------------
            failure_count = SessionManager._update_failure_counter(
                session,
                decision_evaluation
            )
            interview.consecutive_unsuccessful_answers = failure_count

            if interview.current_stage != "resume_based":
                interview.standard_stage_before_resume = interview.current_stage
                session["standard_stage_before_resume"] = interview.current_stage

            session["current_stage"] = interview.current_stage
            session["consecutive_unsuccessful_answers"] = failure_count
            session["scores"][question_id] = stored_evaluation
            if question_id not in session["answered_question_ids"]:
                session["answered_question_ids"].append(question_id)

            # Advance to next question
            next_question = await SessionManager._advance_to_next_question(session)

            if next_question is None:
                # Interview is completed
                interview.status = "completed"
                now_comp = datetime.now(timezone.utc)
                interview.end_time = now_comp
                interview.current_question_id = None
                interview.current_question_metadata = None
                interview.current_followup = None
                interview.current_question_answers = []
                interview.resume_mode = session.get("resume_mode", False)
                interview.transcript = session.get("transcript", [])

                # Generate and persist final report
                session["status"] = "completed"
                session["completed_at"] = now_comp.isoformat()
                try:
                    from app.reporting.report_generator import ReportGenerator
                    report = ReportGenerator.generate_report(session)
                    interview.final_report = report.model_dump()
                    interview.overall_score = report.overall_score
                    interview.recommendation = report.recommendation
                    interview.summary = report.summary
                except Exception as report_err:
                    print(f"Could not generate final report during completion: {report_err}")

                db.flush()
                db.refresh(interview)
                updated_session = SessionManager._model_to_session_dict(interview)
                active_sessions[session_id] = updated_session

                return {
                    "session_id": session_id,
                    "question_id": question_id,
                    "answer": answer_text,
                    "evaluation": stored_evaluation,
                    "decision": decision,
                    "next_action": "INTERVIEW_COMPLETED",
                    "next_question": None,
                    "status": "completed",
                    "answer_classification": decision_evaluation.get("answer_classification"),
                    "consecutive_unsuccessful_answers": failure_count,
                    "resume_mode": interview.resume_mode,
                    "ai_evaluation_successful": hybrid_result["ai_evaluation_successful"]
                }

            # Next question selected: persist it to interview_questions table
            seq_count = (
                db.query(InterviewQuestion)
                .filter(InterviewQuestion.interview_id == interview.id)
                .count()
            )
            next_q_record = InterviewQuestion(
                interview_id=interview.id,
                question_id=next_question["question_id"],
                question_text=next_question["question"],
                competency=next_question.get("competency"),
                difficulty=next_question.get("difficulty"),
                question_type="primary",
                sequence_number=seq_count + 1,
                expected_concepts=next_question.get("expected_concepts"),
            )
            db.add(next_q_record)

            interview.current_question_id = next_question["question_id"]
            interview.current_question_metadata = next_question
            interview.current_stage = session["current_stage"]
            interview.current_followup = None
            interview.followup_count = 0
            interview.current_question_answers = []
            interview.resume_mode = session.get("resume_mode", False)
            interview.resume_question_queue = session.get("resume_question_queue", [])
            interview.resume_questions_generated = session.get("resume_questions_generated", 0)
            interview.transcript = session.get("transcript", [])

            db.flush()
            db.refresh(interview)
            updated_session = SessionManager._model_to_session_dict(interview)
            active_sessions[session_id] = updated_session

            return {
                "session_id": session_id,
                "question_id": question_id,
                "answer": answer_text,
                "evaluation": stored_evaluation,
                "decision": decision,
                "next_action": "NEXT_QUESTION",
                "next_question": next_question,
                "current_stage": interview.current_stage,
                "answer_classification": decision_evaluation.get("answer_classification"),
                "consecutive_unsuccessful_answers": failure_count,
                "resume_mode": interview.resume_mode,
                "ai_evaluation_successful": hybrid_result["ai_evaluation_successful"]
            }

    # --------------------------------------------------
    # GET SESSION (DATABASE PERSISTENCE & CACHE FALLBACK)
    # --------------------------------------------------

    @staticmethod
    def get_session(session_id: str) -> dict | None:
        """
        Retrieves the interview session from persistent storage (or cache).
        Ensures interview history and state survive backend restarts.
        """
        # Always verify persistent database source of truth
        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .options(
                    joinedload(Interview.candidate),
                    joinedload(Interview.questions).joinedload(InterviewQuestion.answers),
                    joinedload(Interview.evaluations).joinedload(Evaluation.question),
                )
                .filter(Interview.session_id == session_id)
                .first()
            )

            if interview is not None:
                session_dict = SessionManager._model_to_session_dict(interview)
                active_sessions[session_id] = session_dict
                return session_dict

        # Fallback to in-memory cache if DB returned None (transient fallback)
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
                session_dict = SessionManager._model_to_session_dict(interview)
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
        """
        Retrieves all interview records from PostgreSQL for recruiter history.
        Survives backend restarts.
        """
        with get_db_context() as db:
            interviews = (
                db.query(Interview)
                .options(joinedload(Interview.candidate))
                .order_by(Interview.created_at.desc())
                .all()
            )

            history = []
            for i in interviews:
                cand = i.candidate
                history.append({
                    "session_id": i.session_id,
                    "candidate_id": cand.candidate_id if cand else "",
                    "candidate_name": cand.candidate_name if cand else "Unknown",
                    "email": cand.email if cand else "",
                    "job_role": i.job_role,
                    "status": i.status,
                    "current_stage": i.current_stage,
                    "overall_score": i.overall_score,
                    "start_time": i.start_time.isoformat() if i.start_time else None,
                    "end_time": i.end_time.isoformat() if i.end_time else None,
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                    "updated_at": i.updated_at.isoformat() if i.updated_at else None,
                })
            return history

    # --------------------------------------------------
    # DELETE INTERVIEW (CASCADE DELETION)
    # --------------------------------------------------

    @staticmethod
    def delete_interview(session_id: str) -> bool:
        """
        Deletes an interview and all associated questions, answers, and evaluations.
        Cascades automatically through foreign keys and ORM relationships.
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

        if session_id in active_sessions:
            del active_sessions[session_id]

        return True
