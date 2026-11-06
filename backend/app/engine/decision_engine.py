
class DecisionEngine:
    """
    Determines the next interview action using answer classification.

    Supported classifications:
        GOOD
        PARTIAL
        IRRELEVANT
        NO_KNOWLEDGE

    Maximum one follow-up per primary question.
    """

    MAX_FOLLOWUPS = 1

    @staticmethod
    def decide_next_action(
        question: dict,
        evaluation: dict,
        followup_count: int = 0,
        explored_concepts: list | None = None
    ) -> dict:

        explored_concepts = explored_concepts or []

        classification = str(
            evaluation.get("answer_classification", "")
        ).upper().strip()

        # --------------------------------------------------
        # CASE 1: CANDIDATE DOES NOT KNOW THE ANSWER
        # --------------------------------------------------

        if classification == "NO_KNOWLEDGE":

            return {
                "action": "NEXT_QUESTION",
                "reason": (
                    "Candidate explicitly indicated that "
                    "they do not know the answer."
                ),
                "target_concepts": [],
                "answer_classification": classification
            }

        # --------------------------------------------------
        # CASE 2: IRRELEVANT ANSWER
        # --------------------------------------------------

        if classification == "IRRELEVANT":

            return {
                "action": "NEXT_QUESTION",
                "reason": (
                    "Candidate's answer was not relevant "
                    "to the question."
                ),
                "target_concepts": [],
                "answer_classification": classification
            }

        # --------------------------------------------------
        # CASE 3: GOOD ANSWER
        # --------------------------------------------------

        if classification == "GOOD":

            return {
                "action": "NEXT_QUESTION",
                "reason": (
                    "Candidate provided a satisfactory answer."
                ),
                "target_concepts": [],
                "answer_classification": classification
            }

        # --------------------------------------------------
        # CASE 4: PARTIALLY CORRECT ANSWER
        # --------------------------------------------------

        if classification == "PARTIAL":

            # Never ask more than one follow-up.
            if followup_count >= DecisionEngine.MAX_FOLLOWUPS:

                return {
                    "action": "NEXT_QUESTION",
                    "reason": (
                        "Maximum follow-up limit reached."
                    ),
                    "target_concepts": [],
                    "answer_classification": classification
                }

            missing_concepts = evaluation.get(
                "missing_concepts", []
            )

            # Find concepts that have not already
            # been explored in previous follow-ups.
            unexplored_concepts = [
                concept
                for concept in missing_concepts
                if concept not in explored_concepts
            ]

            if not unexplored_concepts:

                return {
                    "action": "NEXT_QUESTION",
                    "reason": (
                        "No unexplored concepts remain "
                        "for clarification."
                    ),
                    "target_concepts": [],
                    "answer_classification": classification
                }

            return {
                "action": "FOLLOW_UP",
                "reason": (
                    "Candidate demonstrated partial "
                    "understanding. One clarification "
                    "is appropriate."
                ),
                "target_concepts": unexplored_concepts[:2],
                "answer_classification": classification
            }

        # --------------------------------------------------
        # CASE 5: UNKNOWN OR MISSING CLASSIFICATION
        # --------------------------------------------------

        # Fail safely. Do not return to the old behavior
        # of generating follow-ups from missing concepts.
        return {
            "action": "NEXT_QUESTION",
            "reason": (
                "Answer classification is unavailable. "
                "Moving to the next question safely."
            ),
            "target_concepts": [],
            "answer_classification": (
                classification or "UNCLASSIFIED"
            )
        }
