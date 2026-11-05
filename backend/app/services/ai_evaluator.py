
import json
from json_repair import repair_json

from app.services.openrouter_client import OpenRouterClient
from app.schemas.ai_evaluation import AIEvaluation


class AIEvaluator:

    def __init__(self):
        self.client = OpenRouterClient()

    async def evaluate_answer(
        self,
        question: str,
        expected_concepts: list[str],
        candidate_answer: str,
        candidate_evidence: dict | None = None
    ) -> AIEvaluation:

        evidence_context = json.dumps(
            candidate_evidence or {},
            indent=2
        )

        system_prompt = """
You are an expert technical interviewer.

Evaluate candidate answers objectively.

Return ONLY one valid JSON object.

Required fields:
- technical_correctness
- concept_coverage
- reasoning_quality
- communication_clarity
- matched_concepts
- missing_concepts
- incorrect_statements
- evidence
- strengths
- improvement_areas
- overall_feedback
- confidence

Rules:
1. All four scores must be integers between 0 and 100.
2. Never return empty strings for numerical scores.
3. All list fields must contain strings.
4. overall_feedback must be a non-empty string.
5. confidence must be low, medium, or high.
6. Evidence must be exact excerpts from the candidate answer.
7. Do not invent evidence.
8. Recognize technically correct paraphrases.
9. Evaluate technical correctness, reasoning and communication.
10. Do not make hiring or rejection decisions.
11. Include all expected concepts in matched_concepts or
   missing_concepts as appropriate.

Required JSON structure:

{
  "technical_correctness": 0,
  "concept_coverage": 0,
  "reasoning_quality": 0,
  "communication_clarity": 0,
  "matched_concepts": [],
  "missing_concepts": [],
  "incorrect_statements": [],
  "evidence": [],
  "strengths": [],
  "improvement_areas": [],
  "overall_feedback": "Evaluation feedback",
  "confidence": "medium"
}
"""

        user_prompt = f"""
Evaluate this interview answer.

QUESTION:
{question}

EXPECTED CONCEPTS:
{json.dumps(expected_concepts, indent=2)}

CANDIDATE ANSWER:
{candidate_answer}

POTENTIAL EVIDENCE:
{evidence_context}

Independently verify the evidence.
Do not blindly accept semantic matches.
Return every required field.
Return only valid JSON.
"""

        response = await self.client.generate_response(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        evaluation_data = self._parse_response(response)

        if not isinstance(evaluation_data, dict):
            raise ValueError(
                "AI response must be a JSON object."
            )

        evaluation_data = self._normalize_response(
            evaluation_data
        )

        evaluation_data["evidence"] = self.validate_evidence(
            evaluation_data["evidence"],
            candidate_answer
        )

        try:
            return AIEvaluation.model_validate(evaluation_data)

        except Exception as error:
            raise ValueError(
                f"AI evaluation validation failed: {error}"
            ) from error

    @staticmethod
    def _normalize_response(data: dict) -> dict:

        score_fields = [
            "technical_correctness",
            "concept_coverage",
            "reasoning_quality",
            "communication_clarity"
        ]

        for field in score_fields:

            value = data.get(field)

            if value is None or value == "":
                data[field] = None
                continue

            try:
                if isinstance(value, bool):
                    raise ValueError("Boolean is not a score")

                score = int(value)

                if not 0 <= score <= 100:
                    raise ValueError("Score outside 0-100")

                data[field] = score

            except (ValueError, TypeError):
                data[field] = None

        list_fields = [
            "matched_concepts",
            "missing_concepts",
            "incorrect_statements",
            "evidence",
            "strengths",
            "improvement_areas"
        ]

        for field in list_fields:

            value = data.get(field, [])

            if not isinstance(value, list):
                value = []

            data[field] = [
                str(item)
                for item in value
                if isinstance(item, (str, int, float))
                and not isinstance(item, bool)
            ]

        feedback = data.get("overall_feedback")

        if not isinstance(feedback, str) or not feedback.strip():
            data["overall_feedback"] = (
                "AI evaluation was incomplete. "
                "Manual review is recommended."
            )

        confidence = data.get("confidence")

        if confidence not in ["low", "medium", "high"]:
            data["confidence"] = "low"

        return data

    @staticmethod
    def _parse_response(response: str) -> dict:

        if not response or not response.strip():
            raise ValueError("AI returned an empty response.")

        cleaned = response.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.replace("```json", "", 1)
            cleaned = cleaned.replace("```", "")

        try:
            result = json.loads(cleaned)

            if isinstance(result, dict):
                return result

        except json.JSONDecodeError:
            pass

        print("Warning: Attempting JSON repair...")

        try:
            result = repair_json(
                cleaned,
                return_objects=True
            )

            if isinstance(result, dict):
                return result

        except Exception as error:
            raise ValueError(
                f"Unable to repair AI response: {error}"
            ) from error

        raise ValueError(
            "AI response could not be converted into JSON."
        )

    @staticmethod
    def validate_evidence(
        evidence: list[str],
        candidate_answer: str
    ) -> list[str]:

        validated = []

        normalized_answer = " ".join(
            candidate_answer.split()
        ).casefold()

        for item in evidence:

            normalized_quote = " ".join(
                item.split()
            ).casefold()

            if (
                normalized_quote
                and normalized_quote in normalized_answer
            ):
                validated.append(item)

        return validated
