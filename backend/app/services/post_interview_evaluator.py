from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from app.db.models import Candidate, Evaluation, Interview, InterviewQuestion
from app.db.session import get_db_context
from app.reporting.report_generator import ReportGenerator
from app.services.hybrid_evaluator import HybridEvaluator


class PostInterviewEvaluator:
    """Evaluate persisted interview answers after the candidate finishes."""

    _hybrid_evaluator = None

    @classmethod
    def _get_hybrid_evaluator(cls):
        if cls._hybrid_evaluator is None:
            cls._hybrid_evaluator = HybridEvaluator()
        return cls._hybrid_evaluator

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _build_session_snapshot(session_id: str):
        """Load the interview and its answers before making external LLM calls."""
        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .options(
                    joinedload(Interview.candidate),
                    joinedload(Interview.questions).joinedload(
                        InterviewQuestion.answers
                    ),
                )
                .filter(Interview.session_id == session_id)
                .first()
            )

            if interview is None:
                raise ValueError("Interview session not found.")

            if interview.status != "completed":
                raise ValueError("Only completed interviews can be evaluated.")

            candidate = interview.candidate
            questions = []
            for question in interview.questions:
                if question.question_type != "primary":
                    continue

                answer_parts = [
                    answer.answer_text.strip()
                    for answer in question.answers
                    if answer.answer_text and answer.answer_text.strip()
                ]
                candidate_answer = " ".join(answer_parts).strip()

                # Include every asked primary question. A missing answer is
                # evaluated as an empty response, not silently omitted.
                questions.append({
                    "question_id": question.question_id,
                    "question": question.question_text,
                    "competency": question.competency or "backend_development",
                    "difficulty": question.difficulty or "medium",
                    "expected_concepts": question.expected_concepts or [],
                    "candidate_answer": candidate_answer,
                    "question_record_id": question.id,
                })

            snapshot = {
                "session_id": interview.session_id,
                "candidate": {
                    "candidate_id": candidate.candidate_id if candidate else "",
                    "candidate_name": candidate.candidate_name if candidate else "",
                    "email": candidate.email if candidate else "",
                    "job_role": interview.job_role,
                    "job_description": interview.job_description or "",
                },
                "status": interview.status,
                "transcript": list(interview.transcript or []),
                "questions": questions,
            }

            return snapshot

    @staticmethod
    def _store_evaluation(session_id: str, question_record_id: int, result: dict):
        """Persist the normalized per-question evaluation in the existing table."""
        ai = result.get("ai_evaluation") or {}
        decision = result.get("decision_evaluation") or {}

        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .first()
            )
            if interview is None:
                raise ValueError("Interview disappeared during evaluation.")

            # Makes a retry idempotent for this question.
            db.query(Evaluation).filter(
                Evaluation.interview_id == interview.id,
                Evaluation.question_id == question_record_id,
            ).delete(synchronize_session=False)

            evaluation = Evaluation(
                interview_id=interview.id,
                question_id=question_record_id,
                technical_correctness=ai.get("technical_correctness"),
                concept_coverage=(
                    ai.get("concept_coverage")
                    if ai.get("concept_coverage") is not None
                    else decision.get("concept_coverage")
                ),
                reasoning_quality=ai.get("reasoning_quality"),
                communication_clarity=ai.get("communication_clarity"),
                answer_classification=ai.get("answer_classification")
                or decision.get("answer_classification"),
                matched_concepts=ai.get("matched_concepts")
                or decision.get("matched_concepts", []),
                missing_concepts=ai.get("missing_concepts")
                or decision.get("missing_concepts", []),
                incorrect_statements=ai.get("incorrect_statements", []),
                overall_feedback=ai.get("overall_feedback")
                or decision.get("overall_feedback"),
                confidence=ai.get("confidence"),
                complete_evaluation_json=result,
            )
            db.add(evaluation)
            db.flush()

    @classmethod
    async def run(cls, session_id: str):
        """Run all AI evaluations, then build and persist the final report."""
        with get_db_context() as db:
            interview = (
                db.query(Interview)
                .filter(Interview.session_id == session_id)
                .first()
            )
            if interview is None:
                raise ValueError("Interview session not found.")
            if interview.status != "completed":
                raise ValueError("Interview is not completed.")
            if interview.evaluation_status == "completed" and interview.final_report:
                return interview.final_report
            interview.evaluation_status = "processing"
            db.flush()

        try:
            snapshot = cls._build_session_snapshot(session_id)
            evaluator = cls._get_hybrid_evaluator()

            # Remove any partial evaluations from a previous failed attempt.
            with get_db_context() as db:
                interview = (
                    db.query(Interview)
                    .filter(Interview.session_id == session_id)
                    .first()
                )
                db.query(Evaluation).filter(
                    Evaluation.interview_id == interview.id
                ).delete(synchronize_session=False)

            scores = {}
            for question in snapshot["questions"]:
                try:
                    hybrid_result = await evaluator.evaluate_answer(
                        question={
                            "question_id": question["question_id"],
                            "question": question["question"],
                            "competency": question["competency"],
                            "difficulty": question["difficulty"],
                            "expected_concepts": question["expected_concepts"],
                        },
                        candidate_answer=question["candidate_answer"],
                    )

                    ai_evaluation = hybrid_result.get("ai_evaluation") or {}
                    evaluation_result = {
                        "candidate_answer": question["candidate_answer"],
                        "ai_evaluation": ai_evaluation,
                        "ai_evaluation_successful": bool(
                            hybrid_result.get("ai_evaluation_successful")
                        ),
                        "decision_evaluation": hybrid_result.get(
                            "decision_evaluation", {}
                        ),
                        "hybrid_evaluation": hybrid_result,
                        "evaluated_at": cls._timestamp(),
                    }
                except Exception as error:
                    # Preserve the question in the report and make the failure
                    # visible for manual review instead of losing the report.
                    print(
                        f"Post-interview evaluation failed for "
                        f"{question['question_id']}: {error}"
                    )
                    evaluation_result = {
                        "candidate_answer": question["candidate_answer"],
                        "ai_evaluation": {},
                        "ai_evaluation_successful": False,
                        "decision_evaluation": {
                            "concept_coverage": None,
                            "matched_concepts": [],
                            "missing_concepts": question["expected_concepts"],
                            "answer_classification": "UNAVAILABLE",
                            "overall_feedback": (
                                "AI evaluation was unavailable. Manual review is required."
                            ),
                        },
                        "hybrid_evaluation": {},
                        "evaluation_error": str(error),
                        "evaluated_at": cls._timestamp(),
                    }

                scores[question["question_id"]] = evaluation_result
                cls._store_evaluation(
                    session_id,
                    question["question_record_id"],
                    evaluation_result,
                )

            # Reconstruct the exact session shape expected by ReportGenerator.
            session_for_report = {
                "session_id": snapshot["session_id"],
                "candidate": snapshot["candidate"],
                "status": "completed",
                "transcript": snapshot["transcript"],
                "scores": scores,
                "questions_metadata": {
                    item["question_id"]: {
                        "question_id": item["question_id"],
                        "question": item["question"],
                        "competency": item["competency"],
                        "difficulty": item["difficulty"],
                        "expected_concepts": item["expected_concepts"],
                    }
                    for item in snapshot["questions"]
                },
            }

            report = ReportGenerator.generate_report(session_for_report)
            report_data = report.model_dump()

            with get_db_context() as db:
                interview = (
                    db.query(Interview)
                    .filter(Interview.session_id == session_id)
                    .first()
                )
                if interview is None:
                    raise ValueError("Interview disappeared before report save.")

                interview.final_report = report_data
                interview.overall_score = report.overall_score
                interview.recommendation = report.recommendation
                interview.summary = report.summary
                interview.evaluation_status = "completed"
                db.flush()

            return report_data

        except Exception:
            with get_db_context() as db:
                interview = (
                    db.query(Interview)
                    .filter(Interview.session_id == session_id)
                    .first()
                )
                if interview is not None:
                    interview.evaluation_status = "failed"
                    db.flush()
            raise
