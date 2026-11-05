
class ScoringEngine:
    """
    Calculates advisory scores from successful AI evaluations.

    Local concept matching is never treated as a technical skill score.
    """

    COMPETENCY_WEIGHTS = {
        "communication": 10,
        "practical_experience": 15,
        "project_understanding": 15,
        "python_fundamentals": 20,
        "backend_development": 20,
        "problem_solving": 20,
    }

    # Dimension weights for each competency.
    DIMENSION_WEIGHTS = {
        "communication": {
            "technical_correctness": 10,
            "concept_coverage": 20,
            "reasoning_quality": 20,
            "communication_clarity": 50,
        },
        "practical_experience": {
            "technical_correctness": 35,
            "concept_coverage": 20,
            "reasoning_quality": 30,
            "communication_clarity": 15,
        },
        "project_understanding": {
            "technical_correctness": 35,
            "concept_coverage": 20,
            "reasoning_quality": 30,
            "communication_clarity": 15,
        },
        "python_fundamentals": {
            "technical_correctness": 50,
            "concept_coverage": 20,
            "reasoning_quality": 20,
            "communication_clarity": 10,
        },
        "backend_development": {
            "technical_correctness": 40,
            "concept_coverage": 20,
            "reasoning_quality": 25,
            "communication_clarity": 15,
        },
        "problem_solving": {
            "technical_correctness": 30,
            "concept_coverage": 15,
            "reasoning_quality": 40,
            "communication_clarity": 15,
        },
    }

    @staticmethod
    def _find_ai_evaluation(evaluation):
        """Find AI evaluation inside supported nested result structures."""

        if not isinstance(evaluation, dict):
            return None

        direct = evaluation.get("ai_evaluation")

        if isinstance(direct, dict) and direct:
            successful = evaluation.get("ai_evaluation_successful")

            if successful is not False:
                return direct

        for key in ("hybrid_evaluation", "evaluation", "result"):
            nested = evaluation.get(key)

            if isinstance(nested, dict):
                found = ScoringEngine._find_ai_evaluation(nested)

                if found:
                    return found

        return None

    @staticmethod
    def calculate_weighted_score(dimension_scores, rubric):
        """Calculate a weighted average from available valid scores."""

        if not rubric:
            return None

        weighted_total = 0.0
        evaluated_weight = 0.0

        for dimension, weight in rubric.items():
            score = dimension_scores.get(dimension)

            if score is None:
                continue

            try:
                score = float(score)
            except (TypeError, ValueError):
                continue

            if not 0 <= score <= 100 or weight <= 0:
                continue

            weighted_total += score * weight
            evaluated_weight += weight

        if evaluated_weight == 0:
            return None

        return round(weighted_total / evaluated_weight, 2)

    @staticmethod
    def calculate_question_score(evaluation, question):
        """
        Calculate an advisory score only from a successful AI evaluation.
        """

        ai = ScoringEngine._find_ai_evaluation(evaluation)

        if not ai:
            return None

        competency = question.get("competency", "")

        weights = ScoringEngine.DIMENSION_WEIGHTS.get(
            competency,
            ScoringEngine.DIMENSION_WEIGHTS["backend_development"]
        )

        dimensions = {
            "technical_correctness": ai.get("technical_correctness"),
            "concept_coverage": ai.get("concept_coverage"),
            "reasoning_quality": ai.get("reasoning_quality"),
            "communication_clarity": ai.get("communication_clarity"),
        }

        return ScoringEngine.calculate_weighted_score(
            dimensions,
            weights
        )

    @staticmethod
    def calculate_overall_score(question_scores):
        """
        Return an overall score only when every required question
        has a valid AI-based score.
        """

        if not question_scores:
            return None

        valid_scores = []

        for score in question_scores:
            if score is None:
                return None

            try:
                score = float(score)
            except (TypeError, ValueError):
                return None

            if not 0 <= score <= 100:
                return None

            valid_scores.append(score)

        return round(
            sum(valid_scores) / len(valid_scores),
            2
        )
