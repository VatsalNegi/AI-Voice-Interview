
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

    # --------------------------------------------------
    # LOCAL FALLBACK CLASSIFICATION
    # --------------------------------------------------

    @staticmethod
    def _classify_without_ai(
        rule_result: dict,
        semantic_result: dict,
        contradiction_result: dict
    ) -> str:

        rule_matched = rule_result.get(
            "matched_concepts", []
        )

        semantic_matched = semantic_result.get(
            "matched_concepts", []
        )

        semantic_uncertain = semantic_result.get(
            "uncertain_concepts", []
        )

        has_contradictions = contradiction_result.get(
            "has_contradictions", False
        )

        relevant_evidence = (
            bool(rule_matched)
            or bool(semantic_matched)
            or bool(semantic_uncertain)
            or has_contradictions
        )

        # Local evidence cannot independently prove
        # that an answer is technically correct.
        if relevant_evidence:
            return "PARTIAL"

        return "IRRELEVANT"

    # --------------------------------------------------
    # EVALUATE ANSWER
    # --------------------------------------------------

    async def evaluate_answer(
        self,
        question: dict,
        candidate_answer: str
    ) -> dict:

        expected_concepts = question.get(
            "expected_concepts", []
        )

        # ----------------------------------------------
        # CHECK EXPLICIT NO-KNOWLEDGE ANSWERS
        # ----------------------------------------------

        if self.ai_evaluator.detect_no_knowledge(
            candidate_answer
        ):

            no_knowledge_result = (
                self.ai_evaluator._build_no_knowledge_evaluation(
                    expected_concepts
                )
            )

            ai_data = no_knowledge_result.model_dump()

            decision_evaluation = {
                **ai_data
            }

            return {
                "rule_evaluation": None,
                "semantic_evaluation": None,
                "contradiction_evaluation": None,
                "ai_evaluation": ai_data,
                "ai_evaluation_triggered": False,
                "ai_evaluation_successful": False,
                "ai_error": None,
                "candidate_evidence": {},
                "decision_evaluation": decision_evaluation
            }

        # ----------------------------------------------
        # LAYER 1: RULE-BASED EVALUATION
        # ----------------------------------------------

        rule_result = self.rule_evaluator.evaluate(
            candidate_answer,
            question
        )

        # ----------------------------------------------
        # LAYER 2: SEMANTIC EVALUATION
        # ----------------------------------------------

        semantic_result = (
            self.semantic_evaluator.evaluate_concepts(
                candidate_answer,
                expected_concepts
            )
        )

        # ----------------------------------------------
        # LAYER 3: CONTRADICTION DETECTION
        # ----------------------------------------------

        contradiction_result = (
            self.contradiction_detector.detect(
                candidate_answer,
                expected_concepts
            )
        )

        # ----------------------------------------------
        # COLLECT POTENTIAL EVIDENCE
        # ----------------------------------------------

        candidate_evidence = {}

        rule_evidence_map = rule_result.get(
            "matched_evidence", {}
        )

        semantic_evidence_map = semantic_result.get(
            "evidence", {}
        )

        semantic_similarity_map = semantic_result.get(
            "similarities", {}
        )

        for concept in expected_concepts:

            candidate_evidence[concept] = {

                "rule_based": rule_evidence_map.get(
                    concept, []
                ),

                "semantic": semantic_evidence_map.get(
                    concept
                ),

                "semantic_similarity": (
                    semantic_similarity_map.get(concept)
                )
            }

        # ----------------------------------------------
        # LAYER 4: AI / LLM EVALUATION
        # ----------------------------------------------

        # Every substantive answer receives AI evaluation.

        ai_required = True

        ai_result = None
        ai_data = None
        ai_error = None

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

        # ----------------------------------------------
        # NORMALIZE AI EVALUATION
        # ----------------------------------------------

        if ai_result is not None:

            ai_data = ai_result.model_dump()

            ai_matched = ai_data.get(
                "matched_concepts", []
            )

            ai_missing = ai_data.get(
                "missing_concepts", []
            )

            matched_concepts = (
                ai_matched
                if ai_matched or ai_missing
                else rule_result.get("matched_concepts", [])
            )

            missing_concepts = (
                ai_missing
                if ai_matched or ai_missing
                else rule_result.get("missing_concepts", [])
            )

            answer_classification = ai_data.get(
                "answer_classification",
                "PARTIAL"
            )

            # ------------------------------------------
            # CONTRADICTION SAFEGUARD
            # ------------------------------------------

            if (
                contradiction_result.get("has_contradictions")
                and answer_classification == "GOOD"
            ):

                answer_classification = "PARTIAL"

                ai_data["answer_classification"] = (
                    answer_classification
                )

            decision_evaluation = {

                "matched_concepts": matched_concepts,

                "missing_concepts": missing_concepts,

                "concept_coverage": ai_data.get(
                    "concept_coverage"
                ),

                "technical_correctness": ai_data.get(
                    "technical_correctness"
                ),

                "reasoning_quality": ai_data.get(
                    "reasoning_quality"
                ),

                "communication_clarity": ai_data.get(
                    "communication_clarity"
                ),

                "answer_classification": answer_classification,

                "incorrect_statements": ai_data.get(
                    "incorrect_statements", []
                ),

                "overall_feedback": ai_data.get(
                    "overall_feedback"
                ),

                "confidence": ai_data.get(
                    "confidence", "low"
                )
            }

        else:

            # ------------------------------------------
            # LOCAL FALLBACK
            # ------------------------------------------

            answer_classification = (
                self._classify_without_ai(
                    rule_result,
                    semantic_result,
                    contradiction_result
                )
            )

            decision_evaluation = {

                "matched_concepts": rule_result.get(
                    "matched_concepts", []
                ),

                "missing_concepts": rule_result.get(
                    "missing_concepts", []
                ),

                "concept_coverage": rule_result.get(
                    "concept_coverage"
                ),

                "technical_correctness": None,

                "reasoning_quality": None,

                "communication_clarity": None,

                "answer_classification": answer_classification,

                "incorrect_statements": (
                    contradiction_result.get(
                        "incorrect_claims", []
                    )
                ),

                "overall_feedback": (
                    "AI evaluation was unavailable. "
                    "A conservative local classification "
                    "was used. Manual review is recommended."
                ),

                "confidence": "low"
            }

        # ----------------------------------------------
        # FINAL HYBRID RESULT
        # ----------------------------------------------

        return {

            "rule_evaluation": rule_result,

            "semantic_evaluation": semantic_result,

            "contradiction_evaluation": contradiction_result,

            "ai_evaluation": ai_data,

            "ai_evaluation_triggered": ai_required,

            "ai_evaluation_successful": (
                ai_result is not None
            ),

            "ai_error": ai_error,

            "candidate_evidence": candidate_evidence,

            "decision_evaluation": decision_evaluation
        }
