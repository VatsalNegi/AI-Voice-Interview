
from datetime import datetime, timezone

from app.config.question_bank import QUESTION_BANK
from app.schemas.report import (
    InterviewReport,
    CompetencyScore,
    QuestionEvaluation,
)
from app.reporting.scoring_engine import ScoringEngine


class ReportGenerator:

    @staticmethod
    def _get_question_details(question_id, session=None):
        if session:
            questions_metadata = session.get("questions_metadata", {})
            if question_id in questions_metadata:
                return questions_metadata[question_id]

        for questions in QUESTION_BANK.values():
            for question in questions:
                if question["question_id"] == question_id:
                    return question

        return None

    @staticmethod
    def _get_candidate_answer(session, question_id):
        answers = [
            item["text"]
            for item in session.get("transcript", [])
            if item.get("speaker") == "candidate"
            and item.get("question_id") == question_id
        ]

        return " ".join(answers)

    @staticmethod
    def _get_ai_evaluation(evaluation):
        return ScoringEngine._find_ai_evaluation(evaluation)

    @staticmethod
    def _get_decision_evaluation(evaluation):
        if not isinstance(evaluation, dict):
            return {}

        decision = evaluation.get("decision_evaluation")

        if isinstance(decision, dict):
            return decision

        hybrid = evaluation.get("hybrid_evaluation", {})

        if isinstance(hybrid, dict):
            decision = hybrid.get("decision_evaluation")

            if isinstance(decision, dict):
                return decision

        return evaluation

    @staticmethod
    def _get_concept_coverage(evaluation, decision, ai):
        for source in (decision, evaluation, ai or {}):
            if not isinstance(source, dict):
                continue

            value = source.get("concept_coverage")

            if value is not None:
                try:
                    return max(0, min(100, float(value)))
                except (TypeError, ValueError):
                    pass

        return 0.0

    @staticmethod
    def _get_evidence(evaluation, ai):
        evidence = []

        if ai:
            ai_evidence = ai.get("evidence", [])

            if isinstance(ai_evidence, list):
                evidence.extend(
                    item for item in ai_evidence
                    if isinstance(item, str) and item.strip()
                )

        if isinstance(evaluation, dict):
            matched_evidence = evaluation.get("matched_evidence", {})

            if not matched_evidence:
                hybrid = evaluation.get("hybrid_evaluation", {})

                if isinstance(hybrid, dict):
                    matched_evidence = hybrid.get(
                        "candidate_evidence", {}
                    )

            if isinstance(matched_evidence, dict):
                for value in matched_evidence.values():
                    if isinstance(value, list):
                        evidence.extend(
                            item for item in value
                            if isinstance(item, str) and item.strip()
                        )
                    elif isinstance(value, dict):
                        for nested_value in value.values():
                            if (
                                isinstance(nested_value, str)
                                and nested_value.strip()
                            ):
                                evidence.append(nested_value)

        return list(dict.fromkeys(evidence))

    @staticmethod
    def _get_list(source, key):
        if not isinstance(source, dict):
            return []

        value = source.get(key, [])

        if not isinstance(value, list):
            return []

        return [
            item.strip()
            for item in value
            if isinstance(item, str) and item.strip()
        ]

    @staticmethod
    def generate_report(session):

        if session.get("status") != "completed":
            raise ValueError(
                "Report can only be generated for completed interviews."
            )

        scores = session.get("scores", {})

        if not scores:
            raise ValueError(
                "No evaluation data available for this interview."
            )

        candidate = session["candidate"]

        question_evaluations = []
        competency_data = {}

        overall_strengths = []
        overall_improvements = []

        question_scores = []
        evaluated_question_count = 0
        ai_evaluated_question_count = 0

        for question_id, evaluation in scores.items():

            question = ReportGenerator._get_question_details(
                question_id,
                session
            )

            if question is None:
                continue

            evaluated_question_count += 1

            competency = question["competency"]
            candidate_answer = ReportGenerator._get_candidate_answer(
                session,
                question_id
            )

            ai = ReportGenerator._get_ai_evaluation(evaluation)
            decision = ReportGenerator._get_decision_evaluation(
                evaluation
            )

            if ai:
                ai_evaluated_question_count += 1

            matched = (
                ReportGenerator._get_list(ai, "matched_concepts")
                if ai else
                ReportGenerator._get_list(
                    decision, "matched_concepts"
                )
            )

            missing = (
                ReportGenerator._get_list(ai, "missing_concepts")
                if ai else
                ReportGenerator._get_list(
                    decision, "missing_concepts"
                )
            )

            coverage = ReportGenerator._get_concept_coverage(
                evaluation,
                decision,
                ai
            )

            evidence = ReportGenerator._get_evidence(
                evaluation,
                ai
            )

            if ai:
                strengths = ReportGenerator._get_list(
                    ai, "strengths"
                )

                improvements = ReportGenerator._get_list(
                    ai, "improvement_areas"
                )

                incorrect = ReportGenerator._get_list(
                    ai, "incorrect_statements"
                )

                improvements.extend(
                    f"Review the following missing concept: {item}."
                    for item in missing
                )

                improvements.extend(
                    f"Potentially incorrect statement: {item}"
                    for item in incorrect
                )

                feedback = ai.get(
                    "overall_feedback",
                    "AI evaluation completed."
                )

                confidence = ai.get("confidence", "unknown")

                score = ScoringEngine.calculate_question_score(
                    evaluation,
                    question
                )

                feedback = (
                    f"{feedback} "
                    f"AI confidence: {confidence}. "
                    f"Advisory AI score: "
                    f"{score if score is not None else 'unavailable'}/100. "
                    "Human review is required."
                )

            else:
                strengths = []
                improvements = [
                    f"Further explanation may be needed for: {item}."
                    for item in missing
                ]

                feedback = (
                    "AI evaluation was unavailable for this question. "
                    f"Local concept coverage: {coverage:.2f}%. "
                    "This is not a technical skill score. "
                    "A reviewer must assess the answer manually."
                )

                score = None

            overall_strengths.extend(strengths)
            overall_improvements.extend(improvements)

            question_scores.append(score)

            if competency not in competency_data:
                competency_data[competency] = {
                    "scores": [],
                    "evidence": [],
                    "strengths": [],
                    "improvements": [],
                    "question_count": 0,
                    "ai_question_count": 0,
                }

            data = competency_data[competency]
            data["question_count"] += 1

            if score is not None:
                data["scores"].append(score)

            if ai:
                data["ai_question_count"] += 1

            data["evidence"].extend(evidence)
            data["strengths"].extend(strengths)
            data["improvements"].extend(improvements)

            question_evaluations.append(
                QuestionEvaluation(
                    question_id=question_id,
                    question=question["question"],
                    competency=competency,
                    candidate_answer=candidate_answer,
                    concept_coverage=coverage,
                    strengths=strengths,
                    improvement_areas=list(
                        dict.fromkeys(improvements)
                    ),
                    technical_feedback=feedback,
                )
            )

        # Build a complete competency breakdown.
        competency_scores = []

        for competency, weight in (
            ScoringEngine.COMPETENCY_WEIGHTS.items()
        ):

            data = competency_data.get(
                competency,
                {
                    "scores": [],
                    "evidence": [],
                    "strengths": [],
                    "improvements": [],
                    "question_count": 0,
                    "ai_question_count": 0,
                }
            )

            valid_scores = data["scores"]

            competency_score = (
                round(sum(valid_scores) / len(valid_scores), 2)
                if valid_scores else None
            )

            if competency_score is None:
                feedback = (
                    "No successful AI skill evaluation is available "
                    "for this competency. Manual reviewer assessment "
                    "is required."
                )
            else:
                feedback = (
                    f"Preliminary AI-based competency score: "
                    f"{competency_score}/100. "
                    f"AI evaluated {data['ai_question_count']} "
                    f"of {data['question_count']} question(s). "
                    "This score is advisory and requires human review."
                )

            competency_scores.append(
                CompetencyScore(
                    competency=competency,
                    score=competency_score,
                    weight=weight,
                    evidence=list(dict.fromkeys(data["evidence"])),
                    feedback=feedback,
                )
            )

        # Do not calculate an overall score if any evaluated
        # question lacks a successful AI-based score.
        overall_score = ScoringEngine.calculate_overall_score(
            question_scores
        )

        recommendation = "MANUAL_REVIEW_REQUIRED"

        recommendation_reason = (
            "AI-generated evaluations are preliminary and advisory. "
            "The recruiter or technical reviewer must inspect the "
            "candidate's answers, transcript, supporting evidence, "
            "and any unavailable evaluations before making a hiring "
            "decision. The system does not make hiring or rejection "
            "decisions."
        )

        if overall_score is None:
            summary_score = (
                "A validated overall score is unavailable because "
                "one or more questions do not have successful "
                "AI-based evaluations."
            )
        else:
            summary_score = (
                f"The preliminary AI-based overall score is "
                f"{overall_score}/100."
            )

        summary = (
            f"Interview completed for {candidate['candidate_name']} "
            f"for the {candidate['job_role']} role. "
            f"{evaluated_question_count} question(s) were evaluated, "
            f"with successful AI evaluations for "
            f"{ai_evaluated_question_count} question(s). "
            f"{summary_score} Human review is required."
        )

        return InterviewReport(
            session_id=session["session_id"],
            candidate_id=candidate["candidate_id"],
            candidate_name=candidate["candidate_name"],
            email=candidate["email"],
            job_role=candidate["job_role"],
            overall_score=overall_score,
            recommendation=recommendation,
            recommendation_reason=recommendation_reason,
            competency_scores=competency_scores,
            question_evaluations=question_evaluations,
            overall_strengths=list(
                dict.fromkeys(overall_strengths)
            ),
            areas_for_improvement=list(
                dict.fromkeys(overall_improvements)
            ),
            summary=summary,
            transcript=session.get("transcript", []),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
