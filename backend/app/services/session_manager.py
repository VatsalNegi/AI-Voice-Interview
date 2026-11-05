
from uuid import uuid4
from datetime import datetime, timezone

from app.schemas.interview import InterviewSessionCreate
from app.engine.question_selector import QuestionSelector
from app.engine.decision_engine import DecisionEngine
from app.config.question_bank import QUESTION_BANK
from app.services.hybrid_evaluator import HybridEvaluator


# Temporary in-memory session storage
active_sessions = {}


class SessionManager:

    # Lazy initialization: load the evaluator only when needed.
    _hybrid_evaluator = None

    @classmethod
    def _get_hybrid_evaluator(cls):
        if cls._hybrid_evaluator is None:
            cls._hybrid_evaluator = HybridEvaluator()

        return cls._hybrid_evaluator

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat()

    # --------------------------------------------------
    # BUILD FOLLOW-UP QUESTION
    # --------------------------------------------------

    @staticmethod
    def _build_followup_question(missing_concepts):

        if not missing_concepts:
            return "Could you elaborate a little more on your answer?"

        concepts = [
            concept.replace("_", " ")
            for concept in missing_concepts[:2]
        ]

        if len(concepts) == 1:
            return (
                f"Could you explain a little more about "
                f"{concepts[0]}?"
            )

        return (
            f"Could you explain a little more about "
            f"{concepts[0]} and {concepts[1]}?"
        )

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
    # ADVANCE TO NEXT QUESTION
    # --------------------------------------------------

    @staticmethod
    def _advance_to_next_question(session):

        stages = list(QUESTION_BANK.keys())
        current_stage = session["current_stage"]

        # Try another question in the current stage
        question = QuestionSelector.select_next_question(
            stage=current_stage,
            asked_question_ids=session["asked_question_ids"]
        )

        if question is not None:
            return SessionManager._set_next_question(
                session, question, current_stage
            )

        # Move to the next available stage
        current_index = stages.index(current_stage)

        for stage in stages[current_index + 1:]:

            question = QuestionSelector.select_next_question(
                stage=stage,
                asked_question_ids=session["asked_question_ids"]
            )

            if question is not None:
                return SessionManager._set_next_question(
                    session, question, stage
                )

        # No questions remain
        session["status"] = "completed"
        session["current_question"] = None
        session["current_followup"] = None
        session["completed_at"] = SessionManager._timestamp()

        return None

    # --------------------------------------------------
    # CREATE SESSION
    # --------------------------------------------------

    @staticmethod
    def create_session(session_data: InterviewSessionCreate):

        session_id = str(uuid4())

        session = {
            "session_id": session_id,
            "candidate": session_data.candidate.model_dump(),

            "interview_duration": session_data.interview_duration,
            "language": session_data.language,

            "status": "not_started",
            "current_stage": "introduction",

            "current_question": None,
            "current_followup": None,

            "asked_question_ids": [],
            "answered_question_ids": [],

            "followup_count": 0,
            "current_question_answers": [],

            "transcript": [],
            "scores": {},

            "created_at": SessionManager._timestamp()
        }

        active_sessions[session_id] = session

        return session

    # --------------------------------------------------
    # START SESSION
    # --------------------------------------------------

    @staticmethod
    def start_session(session_id: str):

        session = active_sessions.get(session_id)

        if session is None:
            return None

        if session["status"] != "not_started":
            raise ValueError(
                "Interview has already been started or completed."
            )

        question = QuestionSelector.select_next_question(
            stage=session["current_stage"],
            asked_question_ids=session["asked_question_ids"]
        )

        if question is None:
            raise ValueError(
                f"No questions available for stage: "
                f"{session['current_stage']}"
            )

        session["status"] = "in_progress"
        session["started_at"] = SessionManager._timestamp()

        SessionManager._set_next_question(
            session,
            question,
            session["current_stage"]
        )

        return session

    # --------------------------------------------------
    # SUBMIT AND EVALUATE ANSWER
    # --------------------------------------------------

    @staticmethod
    async def submit_answer(session_id: str, answer_text: str):

        session = active_sessions.get(session_id)

        if session is None:
            raise ValueError("Interview session not found.")

        if session["status"] != "in_progress":
            raise ValueError("Interview is not currently in progress.")

        question = session.get("current_question")

        if question is None:
            raise ValueError("No active question found.")

        question_id = question["question_id"]

        if question_id in session["answered_question_ids"]:
            raise ValueError("This question has already been answered.")

        if not answer_text or not answer_text.strip():
            raise ValueError("Candidate answer cannot be empty.")

        # ----------------------------------------------
        # SAVE CANDIDATE ANSWER IN TRANSCRIPT
        # ----------------------------------------------

        answer_text = answer_text.strip()

        session["transcript"].append({
            "speaker": "candidate",
            "type": "answer",
            "question_id": question_id,
            "text": answer_text,
            "timestamp": SessionManager._timestamp()
        })

        # Store all answers for the current question
        session["current_question_answers"].append(answer_text)

        # Combine original answer and follow-up answers
        combined_answer = " ".join(
            session["current_question_answers"]
        )

        # ----------------------------------------------
        # HYBRID AI EVALUATION
        # ----------------------------------------------

        hybrid_evaluator = SessionManager._get_hybrid_evaluator()

        hybrid_result = await hybrid_evaluator.evaluate_answer(
            question=question,
            candidate_answer=combined_answer
        )

        # ----------------------------------------------
        # PREPARE EVALUATION FOR DECISION ENGINE
        # ----------------------------------------------

        decision_evaluation = hybrid_result[
            "decision_evaluation"
        ].copy()

        # If AI evaluation failed but a contradiction was detected,
        # ensure the relevant concept can still trigger a follow-up.
        contradiction_result = hybrid_result[
            "contradiction_evaluation"
        ]

        if (
            not hybrid_result["ai_evaluation_successful"]
            and contradiction_result["has_contradictions"]
        ):
            missing = decision_evaluation.get(
                "missing_concepts", []
            )

            for contradiction in contradiction_result["contradictions"]:
                concept = contradiction["concept"]

                if concept not in missing:
                    missing.append(concept)

            decision_evaluation["missing_concepts"] = missing

        # ----------------------------------------------
        # STORE COMPLETE EVALUATION
        # ----------------------------------------------

        stored_evaluation = {
            **decision_evaluation,
            "candidate_answer": combined_answer,
            "hybrid_evaluation": hybrid_result,
            "evaluated_at": SessionManager._timestamp()
        }

        session["scores"][question_id] = stored_evaluation

        # ----------------------------------------------
        # DECIDE NEXT ACTION
        # ----------------------------------------------

        decision = DecisionEngine.decide_next_action(
            question=question,
            evaluation=decision_evaluation,
            followup_count=session["followup_count"]
        )

        # ----------------------------------------------
        # CASE 1: ASK FOLLOW-UP
        # ----------------------------------------------

        if decision["action"] == "FOLLOW_UP":

            session["followup_count"] += 1

            followup_question = (
                SessionManager._build_followup_question(
                    decision["target_concepts"]
                )
            )

            session["current_followup"] = followup_question

            session["transcript"].append({
                "speaker": "interviewer",
                "type": "follow_up",
                "question_id": question_id,
                "text": followup_question,
                "timestamp": SessionManager._timestamp()
            })

            return {
                "session_id": session_id,
                "question_id": question_id,
                "answer": answer_text,
                "evaluation": stored_evaluation,
                "decision": decision,
                "next_action": "FOLLOW_UP",
                "next_question": followup_question,
                "followup_count": session["followup_count"],
                "ai_evaluation_successful": hybrid_result[
                    "ai_evaluation_successful"
                ]
            }

        # ----------------------------------------------
        # CASE 2: MOVE TO NEXT QUESTION
        # ----------------------------------------------

        session["answered_question_ids"].append(question_id)

        next_question = SessionManager._advance_to_next_question(
            session
        )

        if next_question is None:

            return {
                "session_id": session_id,
                "question_id": question_id,
                "answer": answer_text,
                "evaluation": stored_evaluation,
                "decision": decision,
                "next_action": "INTERVIEW_COMPLETED",
                "next_question": None,
                "status": "completed",
                "ai_evaluation_successful": hybrid_result[
                    "ai_evaluation_successful"
                ]
            }

        return {
            "session_id": session_id,
            "question_id": question_id,
            "answer": answer_text,
            "evaluation": stored_evaluation,
            "decision": decision,
            "next_action": "NEXT_QUESTION",
            "next_question": next_question,
            "current_stage": session["current_stage"],
            "ai_evaluation_successful": hybrid_result[
                "ai_evaluation_successful"
            ]
        }

    # --------------------------------------------------
    # GET SESSION
    # --------------------------------------------------

    @staticmethod
    def get_session(session_id: str):

        return active_sessions.get(session_id)

    # --------------------------------------------------
    # UPDATE SESSION
    # --------------------------------------------------

    @staticmethod
    def update_session(session_id: str, updates: dict):

        session = active_sessions.get(session_id)

        if session is None:
            return None

        session.update(updates)

        return session
