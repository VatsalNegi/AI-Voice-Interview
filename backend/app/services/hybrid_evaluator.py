
from app.engine.answer_evaluator import AnswerEvaluator
from app.engine.contradiction_detector import ContradictionDetector
from app.services.semantic_evaluator import SemanticEvaluator
from app.services.ai_evaluator import AIEvaluator


class HybridEvaluator:

    def __init__(self):

        self.rule_evaluator = AnswerEvaluator()
        self.semantic_evaluator = SemanticEvaluator()
        self.contradiction_detector = ContradictionDetector()
        self.ai_evaluator = AIEvaluator()

    async def evaluate_answer(
        self,
        question: dict,
        candidate_answer: str
    ) -> dict:

        expected_concepts = question.get(
            "expected_concepts", []
        )

        # -----------------------------------------
        # LAYER 1: RULE-BASED EVALUATION
        # -----------------------------------------

        rule_result = self.rule_evaluator.evaluate(
            candidate_answer,
            question
        )

        # -----------------------------------------
        # LAYER 2: SEMANTIC EVALUATION
        # -----------------------------------------

        semantic_result = self.semantic_evaluator.evaluate_concepts(
            candidate_answer,
            expected_concepts
        )

        # -----------------------------------------
        # LAYER 3: CONTRADICTION DETECTION
        # -----------------------------------------

        contradiction_result = self.contradiction_detector.detect(
            candidate_answer,
            expected_concepts
        )

        # -----------------------------------------
        # COLLECT POTENTIAL EVIDENCE
        # -----------------------------------------

        candidate_evidence = {}

        for concept in expected_concepts:

            rule_evidence = rule_result[
                "matched_evidence"
            ].get(concept, [])

            semantic_evidence = semantic_result[
                "evidence"
            ].get(concept)

            candidate_evidence[concept] = {
                "rule_based": rule_evidence,
                "semantic": semantic_evidence,
                "semantic_similarity": semantic_result[
                    "similarities"
                ].get(concept)
            }

        # -----------------------------------------
        # DECIDE WHETHER AI EVALUATION IS REQUIRED
        # -----------------------------------------

        uncertain_concepts = semantic_result.get(
            "uncertain_concepts", []
        )

        semantic_missing = semantic_result.get(
            "missing_concepts", []
        )

        rule_missing = rule_result.get(
            "missing_concepts", []
        )

        has_contradictions = contradiction_result.get(
            "has_contradictions", False
        )

        ai_required = (
            bool(uncertain_concepts)
            or bool(semantic_missing)
            or bool(rule_missing)
            or has_contradictions
        )

        # -----------------------------------------
        # LAYER 4: AI / LLM EVALUATION
        # -----------------------------------------

        ai_result = None
        ai_error = None

        if ai_required:

            try:

                ai_result = await self.ai_evaluator.evaluate_answer(
                    question=question.get("question", ""),
                    expected_concepts=expected_concepts,
                    candidate_answer=candidate_answer,
                    candidate_evidence=candidate_evidence
                )

                print("AI evaluation completed successfully.")

            except Exception as error:

                ai_error = str(error)

                print(
                    f"AI evaluation failed: {ai_error}"
                )

        # -----------------------------------------
        # NORMALIZE AI EVALUATION
        # -----------------------------------------

        if ai_result:

            ai_data = ai_result.model_dump()

            # Use AI concept evaluation when available.
            # Otherwise, fall back to rule-based results.

            ai_matched = ai_data.get(
                "matched_concepts", []
            )

            ai_missing = ai_data.get(
                "missing_concepts", []
            )

            matched_concepts = (
                ai_matched
                if ai_matched or ai_missing
                else rule_result["matched_concepts"]
            )

            missing_concepts = (
                ai_missing
                if ai_matched or ai_missing
                else rule_result["missing_concepts"]
            )

            ai_coverage = ai_data.get(
                "concept_coverage"
            )

            decision_evaluation = {

                "matched_concepts": matched_concepts,

                "missing_concepts": missing_concepts,

                "concept_coverage": (
                    ai_coverage
                    if ai_coverage is not None
                    else rule_result["concept_coverage"]
                ),

                "technical_correctness": ai_data.get(
                    "technical_correctness"
                ),

                "reasoning_quality": ai_data.get(
                    "reasoning_quality"
                ),

                "communication_clarity": ai_data.get(
                    "communication_clarity"
                )
            }

        else:

            # -------------------------------------
            # LOCAL FALLBACK
            # -------------------------------------

            decision_evaluation = {

                "matched_concepts": rule_result[
                    "matched_concepts"
                ],

                "missing_concepts": rule_result[
                    "missing_concepts"
                ],

                "concept_coverage": rule_result[
                    "concept_coverage"
                ],

                "technical_correctness": None,

                "reasoning_quality": None,

                "communication_clarity": None
            }

        # -----------------------------------------
        # FINAL HYBRID RESULT
        # -----------------------------------------

        return {

            "rule_evaluation": rule_result,

            "semantic_evaluation": semantic_result,

            "contradiction_evaluation": contradiction_result,

            "ai_evaluation": (
                ai_result.model_dump()
                if ai_result is not None
                else None
            ),

            "ai_evaluation_triggered": ai_required,

            "ai_evaluation_successful": (
                ai_result is not None
            ),

            "ai_error": ai_error,

            "candidate_evidence": candidate_evidence,

            "decision_evaluation": decision_evaluation
        }
