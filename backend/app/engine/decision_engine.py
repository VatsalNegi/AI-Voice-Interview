
class DecisionEngine:

    @staticmethod
    def decide_next_action(
        question,
        evaluation,
        followup_count=0,
        explored_concepts=None
    ):

        max_followups = question.get("max_followups", 2)

        missing_concepts = evaluation.get(
            "missing_concepts", []
        )

        explored_concepts = explored_concepts or []

        # All expected concepts have been covered
        if not missing_concepts:
            return {
                "action": "NEXT_QUESTION",
                "reason": "All expected concepts have been covered.",
                "target_concepts": []
            }

        # Maximum follow-ups have already been asked
        if followup_count >= max_followups:
            return {
                "action": "NEXT_QUESTION",
                "reason": "Maximum follow-up limit reached.",
                "target_concepts": []
            }

        # Avoid repeating concepts already explored
        unexplored_concepts = [
            concept
            for concept in missing_concepts
            if concept not in explored_concepts
        ]

        if not unexplored_concepts:
            return {
                "action": "NEXT_QUESTION",
                "reason": "All missing concepts have already been explored.",
                "target_concepts": []
            }

        # Ask a follow-up about remaining missing concepts
        return {
            "action": "FOLLOW_UP",
            "reason": "Some expected concepts need further exploration.",
            "target_concepts": unexplored_concepts[:2]
        }
