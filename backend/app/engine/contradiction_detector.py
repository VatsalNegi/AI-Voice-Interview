
class ContradictionDetector:

    # Statements supporting the expected concept
    POSITIVE_PATTERNS = {

        "List is mutable": [
            "lists are mutable",
            "list is mutable",
            "list can be modified",
            "lists can be modified",
            "list can be changed",
            "we can modify a list",
            "we can modify them",
            "we can change a list",
        ],

        "Tuple is immutable": [
            "tuples are immutable",
            "tuple is immutable",
            "tuple cannot be modified",
            "tuples cannot be modified",
            "tuple cannot be changed",
            "cannot reassign tuple items",
        ],

        "Lists use square brackets": [
            "lists use square brackets",
            "list uses square brackets",
            "lists are written using square brackets",
            "list is written using square brackets",
        ],

        "Tuples use parentheses": [
            "tuples use parentheses",
            "tuple uses parentheses",
            "tuples are written using parentheses",
            "tuple is written using parentheses",
        ],
    }

    # Statements opposing the expected concept
    NEGATIVE_PATTERNS = {

        "List is mutable": [
            "lists are immutable",
            "list is immutable",
            "lists cannot be modified",
            "list cannot be modified",
            "lists cannot be changed",
            "list cannot be changed",
            "cannot modify a list",
        ],

        "Tuple is immutable": [
            "tuples are mutable",
            "tuple is mutable",
            "tuples can be modified",
            "tuple can be modified",
            "tuples can be changed",
            "tuple can be changed",
            "can modify a tuple",
        ],

        "Lists use square brackets": [
            "lists use parentheses",
            "list uses parentheses",
            "lists are written using parentheses",
            "lists use curly braces",
        ],

        "Tuples use parentheses": [
            "tuples use square brackets",
            "tuple uses square brackets",
            "tuples are written using square brackets",
            "tuples use curly braces",
        ],
    }

    @staticmethod
    def normalize(text: str) -> str:
        return " ".join(text.lower().split())

    def detect(
        self,
        candidate_answer: str,
        expected_concepts: list[str]
    ) -> dict:

        answer = self.normalize(candidate_answer)

        detected_contradictions = []
        incorrect_claims = []

        for concept in expected_concepts:

            positive_patterns = self.POSITIVE_PATTERNS.get(
                concept,
                []
            )

            negative_patterns = self.NEGATIVE_PATTERNS.get(
                concept,
                []
            )

            positive_matches = [
                pattern
                for pattern in positive_patterns
                if pattern in answer
            ]

            negative_matches = [
                pattern
                for pattern in negative_patterns
                if pattern in answer
            ]

            # Incorrect claims are recorded independently.
            for pattern in negative_matches:

                incorrect_claims.append({
                    "concept": concept,
                    "incorrect_statement": pattern,
                    "reason": (
                        "This statement opposes the expected concept."
                    )
                })

            # An internal contradiction requires BOTH sides.
            if positive_matches and negative_matches:

                detected_contradictions.append({
                    "concept": concept,
                    "supporting_statements": positive_matches,
                    "conflicting_statements": negative_matches,
                    "reason": (
                        "The candidate made conflicting statements "
                        "about the same concept."
                    )
                })

        return {
            "has_contradictions": bool(
                detected_contradictions
            ),
            "contradictions": detected_contradictions,
            "incorrect_claims": incorrect_claims
        }
